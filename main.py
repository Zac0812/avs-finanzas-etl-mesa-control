# main.py

import pandas as pd
import datetime as dt
import traceback  # Importar el módulo traceback

# Importar módulos personalizados
from config import SICAF_SERVER, SICAF_DB, INFOR_SERVER, INFOR_DB
from data_sources import (
    GoogleSheetFetcher, ConnCGestion,  # classes
    fetch_data_from_oracle, fetch_data_from_sql_trusted  # functions
)
# functions
from data_processing import (
    limpiar_columnas, aggregate_payment_data,
    preprocess_inventory_data, votar_fechas, process_last_income,
    clean_NoSerie, _determinar_fecha
)

# --- CONFIGURACIÓN INICIAL ---
# jupyter notebook remove scientific notation (Se mantiene en data_processing.py)
# pd.set_option('display.float_format', lambda x: '%.3f' % x)


# --- Consultas SQL ---
# Consulta SICA/Flota (db_autos)
SQL_AUTOS = """
select RANK() OVER (PARTITION BY s.NoSerie ORDER BY s.MVA) AS IdRank,
s.MVA,s.NoSerie,S.LocaFechaPropiedad,S.LocaPropiedad,S.LocaTipoPropiedad
from (select v.NumeroEconomico MVA ,v.NumeroSerie NoSerie,v.FechaCompra,
v.FechaInicioOperacion,v.FechaBaja,v.FinArren_Fecha LocaFechaPropiedad,isnull(o.Nombre,'NA') LocaPropiedad,
case when o.EsFinanciera=1 then 'Financiera' 
when o.EsFinanciera=0 then 'Propiedad' else 'NA' end as LocaTipoPropiedad,
v.Grupo,v.TipoTransmision, v.TipoCarroceria Category,
p.Fabricante,p.Marca,p.Version,p.Modelo,
s.SucClave,s.DistClave
from DM_FlotaVehiculos.Data.vw_facVehiculos v 
left outer join DM_FlotaVehiculos.Data.vw_dimPlantillas p on p.dimPlantillaId=v.dimPlantillaId
left outer join DM_FlotaVehiculos.data.vw_dimSucursales s on s.dimSucursalId=v.dimSucursalId_Loca
left outer join DM_FlotaVehiculos.data.vw_dimPropietario o on v.dimPropietarioId=o.dimPropietarioId
where o.Nombre is not null
) s
"""
# Consulta RAC (db_rac)
SQL_RAC = """
select v.NumeroEconomico NumEconomico,v.NumeroSerie NoSerie,c.FechaCI MaxCheckIn
from DM_FlotaVehiculos.Data.vw_facVehiculosStats s
left outer join DM_FlotaVehiculos.Data.vw_facVehiculos v on v.facVehiculoId=s.facVehiculoId
left outer join DM_ContratosRAC.Data.vw_facContratos c on c.facContratoId =s.facContratoId
where s.facContratoId is not null 
"""
# Consulta NetSuite LSG (db_lsg)
SQL_LSG = """
select d.class UNegocio,m.name MVA,m.custrecord_ari_numerodeserie NoSerie, max(t.trandate) trandate
from transactionLine d
inner join transaction t on t.id=d.transaction 
inner join CUSTOMRECORD_ARI_MVA_ARIETE m on m.id = d.custcol_ari_linea_mva
inner join Account a on d.expenseaccount = a.id
inner join accountingPeriod p on t.postingperiod=p.id
where d.expenseaccount=387 and d.subsidiary =2 and d.class in (5,6)  /*5=LSG y 6 =SUB*/
and t.posting ='T' and p.startdate > TO_DATE('2021/12/31 10:10:00','YYYY/MM/DD HH:MI:SS') 
group by d.class,m.name ,m.custrecord_ari_numerodeserie
"""
# Consulta NetSuite Control de Vtas (db_ControlVtas)
SQL_CONTROL_VTAS = """
SELECT Ventas.id IdSalesCar,MVA.custrecord_ari_mva_ariete_registro MVA,Ventas.externalid NumSerie,MVA.custrecord_ari_art IdArticulo,
Compania.custrecord_mx_sat_registered_name AS Propietario,
Cliente.fullname Cliente,Producto.name Canal, Cliente.custentity_ari_fiscal VerificacionFiscal,
Ventas.custrecord_ari_carsales_documentation_ok RecepcionDocumentacion,
MVA.custrecord_ari_mva_validado MVAValidado,
OrdenVenta.tranid OrdenVenta,
OrdenVenta.trandate SalesOrderDate, 
--Ventas.custrecord_ari_carsales_terminoventa SalesOrderTermPayment,
case when COALESCE(PayTerm.name,'NA') ='NA' then 'NA' when PayTerm.name='CONTADO' then 'Contado'  else 'CRÉDITO' end SalesOrderTermPayment,
Factura.id IdHeadFac,Factura.tranid Factura,Factura.transactionnumber FacturaSAT, 
Factura.trandate FechaFactura,
Factura.custbody_nso_cfdi_estado cfdi_estado,
p.startdate PeriodDate,
PaymentTerm.custrecord_mx_sat_pt_code SAT_PayTerm,
Ventas.custrecord_ari_carsales_subtotal SubtotalCtl,Ventas.custrecord_ari_carsales_total TotalCtl,
EstadoFactura.name EstadoFactura,
Gerente.entityid GerenteControlVenta,
Ventas.created Creado,Ventas.lastmodified Modificado,
Modif.fullname ModificadoPor,
GerenteOrdenVenta.entityid GerenteOrdenVenta,
EstadoOrdenVenta.name EstadoOrdenVenta,
Ventas.custrecord_ari_carsales_month MesPromesa,Agno.name AgnoPromesa,
OrdenVenta.foreigntotal SalesOrder_Total,Factura.foreigntotal as Invoice_Total,
--Factura.foreignamountunpaid SaldoPendiente
Factura.foreignamountpaid AmountPaid,Factura.foreignamountunpaid AmounUnPaid
FROM CUSTOMRECORD_ARI_CARSALES Ventas
LEFT JOIN Customer Cliente ON Cliente.id = Ventas.custrecord_ari_carsales_customer
LEFT JOIN Contact Contacto ON Contacto.id = Ventas.custrecord_ari_carsales_customer_contact
LEFT JOIN transaction Factura ON Factura.id = Ventas.custrecord_ari_carsales_mva_invoce
LEFT JOIN accountingPeriod p on Factura.postingperiod=p.id
LEFT JOIN employee Gerente ON Gerente.id = Ventas.custrecord_ari_carsales_manager
LEFT JOIN entity Modif ON Modif.id = Ventas.lastmodifiedby
LEFT JOIN CUSTOMRECORD_ARI_MVA_ARIETE MVA ON MVA.id = Ventas.custrecord_ari_carsales_mva
LEFT JOIN transaction OrdenVenta ON OrdenVenta.id = Ventas.custrecord_ari_carsales_mva_salesorder
--LEFT JOIN term on OrdenVenta.terms = term.id
--terminos de pago del control de venta 
LEFT JOIN CUSTOMLIST3162 PayTerm on PayTerm.id=Ventas.custrecord_ari_carsales_terminoventa
LEFT JOIN Subsidiary Compania ON Compania.id = MVA.custrecord_ari_mva_property_owner
LEFT JOIN CUSTOMLIST_ARI_CARSALES_PRODUCT Producto ON Producto.id = Ventas.custrecord_ari_carsales_product
LEFT JOIN CUSTOMLIST_ARI_CARSALES_REQUEST Solicitud ON Solicitud.id = Ventas.custrecord_ari_carsales_request
LEFT JOIN TransactionStatus EstadoFactura ON EstadoFactura.id = Factura.status AND EstadoFactura.trantype = Factura.type
LEFT JOIN employee GerenteOrdenVenta ON GerenteOrdenVenta.id = OrdenVenta.employee
LEFT JOIN TransactionStatus EstadoOrdenVenta ON EstadoOrdenVenta.id = OrdenVenta.status AND EstadoOrdenVenta.trantype = OrdenVenta.type
LEFT JOIN CUSTOMRECORD_MX_SAT_PAYMENT_TERM PaymentTerm on Factura.custbody_mx_txn_sat_payment_term=PaymentTerm.id
LEFT JOIN CUSTOMLISTCUSTLIST_ARI_CARSALES_YEAR Agno on Ventas.custrecordcustrecord_ari_carsales_year=Agno.id

"""
# New query
SQL_CONTROL_VTAS_LINEAS = """
select distinct Ventas.custrecord_ari_carsales_mva_invoce IdHeadFac,d.class,u.fullname Uni_Negoc
FROM CUSTOMRECORD_ARI_CARSALES Ventas
left outer join transactionLine d on d.transaction=Ventas.custrecord_ari_carsales_mva_invoce
left outer join Classification u on d.class=u.id
"""

# Consulta NetSuite Pagos Clientes (db_payment)
SQL_PAGOS = """
select distinct nd.nextdoc,nd.previousdoc ,t.tranid,t.type,t.recordType,t.trandate,
ts.fullname full_nameTransType, ts.name TransType
from NextTransactionLink nd
left outer join transaction t on t.id=nd.nextdoc and t.type in ('CustPymt','CustCred','Journal')
left outer join accountingPeriod p on t.postingperiod=p.id
--join transactionLine d on t.id=d.transaction
left outer join TransactionStatus ts on t.status = ts.id and t.type = ts.trantype and t.customtype = ts.trancustomtype
where nd.linktype in ('Payment')  
and p.startdate > TO_DATE('2023/12/31 10:10:00','YYYY/MM/DD HH:MI:SS')  
"""
# Consulta NetSuite MVA (db_MVAOracle)
SQL_MVA_ORACLE = """
select m.id,m.custrecord_ari_clavevehicular CveVehicular,m.custrecord_ari_mva_ariete_registro Registro,
m.isinactive,m.name MVA,
m.custrecord_ari_numerodeserie NoSerie,g.name Gpo,
m.custrecord_ari_mva_property_date FechaPropiedad,
s.name Propiedad,i.fullname Articulo, m.custrecord_ari_mva_validado FactVerify,
e.name Estatus
from CUSTOMRECORD_ARI_MVA_ARIETE m
left outer join CUSTOMLISTARI_MVA_GRUPO g on m.custrecord_ari_mva_grupo=g.id 
left outer join Subsidiary s on m.custrecord_ari_mva_property_owner=s.id
left outer join item i on m.custrecord_ari_art= i.id
left outer join CUSTOMLIST_ARI_ESTAUTO_LIST e on m.custrecord_ari_estauto=e.id
"""
# Consulta NetSuite Vendor Bill (db_VendorBill)
SQL_VENDOR_BILL = """
select t.id IdHead,d.id IdDetail,d.subsidiary,t.type,t.recordType,t.createddate ,t.trandate ,t.tranid,
t.postingperiod ,t.custbody_nso_motivo_pago_bbva MotivoPago,
p.startdate PeriodDate,d.expenseaccount,
m.name MVA_Name,m.custrecord_ari_numerodeserie NoSerie,
m2.name MVAItem,m2.custrecord_ari_numerodeserie NoSerieItem,
t.abbrevtype,d.item,i.itemid,i.totalquantityonhand,d.memo MemoDet,
t.entity,e.altname Cliente,e.type TypeEntity,d.createdfrom,
ts.fullname full_nameTransType, ts.name TransType,t.custbody_mx_cfdi_uuid ,
t.custbody_nso_cfdi_estado,t.custbody_mx_cfdi_certify_timestamp,t.custbody_mx_txn_sat_payment_term SAT_PayTerm,
al.amount*(-1) amount, v.entityid as Vendedor
from transactionLine d
left outer join transaction t on t.id=d.transaction 
left outer join accountingPeriod p on t.postingperiod=p.id
left outer join Account a on d.expenseaccount = a.id
left outer join TransactionAccountingLine al on d.id = al.transactionline and d.transaction = al.transaction
left outer join CUSTOMRECORD_ARI_MVA_ARIETE m on m.id = d.custcol_ari_linea_mva
left outer join entity  e on t.entity =e.id
left outer join item i on d.item=i.id
left outer join Employee v on v.id=t.employee
left outer join CUSTOMRECORD_ARI_MVA_ARIETE m2 on  i.id = m2.custrecord_ari_art
left outer join TransactionStatus ts on t.status = ts.id and t.type = ts.trantype and t.customtype = ts.trancustomtype
where  t.type='VendBill'
and (
-- 339 24601 Pasivo por Arrendamiento CP Vehiculos y 335 24120 Otros Préstamos Bancarios Corto Plazo  
--vamos a considerar solo registros antes del 31dic25 dado que en Enero las cuentas de pasivo ahora tiene el registro de las rentas por mva
(d.expenseaccount in (335,339)  and p.startdate > TO_DATE('2022/12/31 10:10:00','YYYY/MM/DD HH:MI:SS') 
and t.postingperiod<=188 and d.item in (2003,2004,3531,3533) )
or 
--259 13100 Inventario Vehículos y 1253 16300 Vehiculos Activo Fijo
(d.expenseaccount in (259,1253)  and p.startdate > TO_DATE('2025/01/31 10:10:00','YYYY/MM/DD HH:MI:SS') )
)
"""
# Consulta Infor (db_infor)
SQL_INFOR = """
select m.site_ref,m.fa_num,m.type,m.Uf_Mva,m.serial,m.tag,m.fa_class,m.acq_date,m.fa_stat,m.Uf_Auto,m.Uf_TipoAuto,m.Uf_UnitCode4,m.dispose_date,m.date_to_start_depr,m.life,m.inv_date,m.fa_desc,
c.amount,c.cost_type,c.cost_desc,c.uf_Factura,
d.accum_depr,d.ytd_depr,d.curr_depr,d.units_tot,d.units_depr,
iif(d.units_depr>0,d.accum_depr/d.units_depr,0) Dep_Mensual,d.lst_dep_date
from famaster_mst m
left outer join dbo.fadepr_mst d on m.fa_num=d.fa_num
left outer join dbo.facost_mst c on m.fa_num=c.fa_num
where m.fa_class in ('INV','AUTO')
union all
select m.site_ref,m.fa_num,m.type,m.Uf_Mva,m.serial,m.tag,m.fa_class,m.acq_date,m.fa_stat,m.Uf_Auto,m.Uf_TipoAuto,m.Uf_UnitCode4,m.dispose_date,m.date_to_start_depr,m.life,m.inv_date,m.fa_desc,
c.amount,c.cost_type,c.cost_desc,c.uf_Factura,
d.accum_depr,d.ytd_depr,d.curr_depr,d.units_tot,d.units_depr,
iif(d.units_depr>0,d.accum_depr/d.units_depr,0) Dep_Mensual,d.lst_dep_date
from DRIVEN_App.dbo.famaster_mst m
left outer join DRIVEN_App.dbo.fadepr_mst d on m.fa_num=d.fa_num
left outer join DRIVEN_App.dbo.facost_mst c on m.fa_num=c.fa_num
union all
select m.site_ref,m.fa_num,m.type,m.Uf_Mva,m.serial,m.tag,m.fa_class,m.acq_date,m.fa_stat,m.Uf_Auto,m.Uf_TipoAuto,m.Uf_UnitCode4,m.dispose_date,m.date_to_start_depr,m.life,m.inv_date,m.fa_desc,
c.amount,c.cost_type,c.cost_desc,c.uf_Factura,
d.accum_depr,d.ytd_depr,d.curr_depr,d.units_tot,d.units_depr,
iif(d.units_depr>0,d.accum_depr/d.units_depr,0) Dep_Mensual,d.lst_dep_date
from GOMEXTRA_APP.dbo.famaster_mst m
left outer join GOMEXTRA_APP.dbo.fadepr_mst d on m.fa_num=d.fa_num
left outer join GOMEXTRA_APP.dbo.facost_mst c on m.fa_num=c.fa_num
"""


def extract_data():
    """Extrae datos de todas las fuentes."""
    print("Iniciando extracción de datos...")

    sheet_fetcher = GoogleSheetFetcher()

    print("Tesorería Sheet")
    # 1. Tesorería (Google Sheets)
    # https://docs.google.com/spreadsheets/d/1JBg86i382uVszRFK0WzexN5K5j18eyXF6QjDorraDrA/edit?gid=0#gid=0cl
    db_Tesoreria = sheet_fetcher.get_sheet_df(
        id_spread_sheet="1JBg86i382uVszRFK0WzexN5K5j18eyXF6QjDorraDrA", rangeSheet="Prioridad Pago Semanal!A1:P2500")

    print("Contabilidad Sheet")
    # 2. Contabilidad (Google Sheets - Compra Ari/Dri)
    #2025: https://docs.google.com/spreadsheets/d/1cmBX5t0-YW4jjhM-cjjXBV08AQfsBI2i_WxVopw6uxo/edit?gid=1561068017#gid=1561068017
    db_ComprasAri = sheet_fetcher.get_sheet_df(
        id_spread_sheet="1cmBX5t0-YW4jjhM-cjjXBV08AQfsBI2i_WxVopw6uxo", rangeSheet="ARIETE_COMPRAS!A3:T2500")
    db_ComprasDri = sheet_fetcher.get_sheet_df(
        id_spread_sheet="1cmBX5t0-YW4jjhM-cjjXBV08AQfsBI2i_WxVopw6uxo", rangeSheet="DRIVEN COMPRAS!A5:T2500")
    #2026: https://docs.google.com/spreadsheets/d/1x3THyk_YehIRZ3wOPDskBgwS18MOi1DRJQySG3oRDFs/edit?gid=452898770#gid=452898770
    db_ComprasAri26 = sheet_fetcher.get_sheet_df(
        id_spread_sheet="1x3THyk_YehIRZ3wOPDskBgwS18MOi1DRJQySG3oRDFs", rangeSheet="ARIETE_COMPRAS!A3:U2500")
    db_ComprasDri26 = sheet_fetcher.get_sheet_df(
        id_spread_sheet="1x3THyk_YehIRZ3wOPDskBgwS18MOi1DRJQySG3oRDFs", rangeSheet="DRIVEN COMPRAS!A5:U2500")
    db_ComprasAri=pd.concat([db_ComprasAri, db_ComprasAri26], axis=0, ignore_index=True)
    db_ComprasDri = pd.concat([db_ComprasDri, db_ComprasDri26], axis=0, ignore_index=True)


    print("Entregas Sheet")
    # 3. Maestro de entregas
    # https://docs.google.com/spreadsheets/d/1VnMIrkBQWKz_FtL3hkBEpIvMliR_U_NoCT7j8ocBsj8/edit?gid=1589888790#gid=1589888790
    db_Entregas = sheet_fetcher.get_sheet_df(id_spread_sheet="1VnMIrkBQWKz_FtL3hkBEpIvMliR_U_NoCT7j8ocBsj8",
                                             rangeSheet="Avance de Entregas!A5:X3000")

    print("Localización DW")
    # 3. Localización (SQL Server SICAF/Flota - db_autos)
    db_autos = fetch_data_from_sql_trusted(SICAF_SERVER, SICAF_DB, SQL_AUTOS)

    print("RAC DW")
    # 4. Last Check In RAC (SQL Server SICA/Flota - db_rac)
    db_rac = fetch_data_from_sql_trusted(SICAF_SERVER, SICAF_DB, SQL_RAC)

    print("Oracle Source")
    # 5. NetSuite (Oracle)
    print(" MVA")
    db_MVAOracle = fetch_data_from_oracle(SQL_MVA_ORACLE)
    print(" Control")
    db_ControlVtas = fetch_data_from_oracle(SQL_CONTROL_VTAS)
    print(" Control Lineas")
    db_ControlVtasLineas = fetch_data_from_oracle(SQL_CONTROL_VTAS_LINEAS)
    print(" Pagos")
    db_payment = fetch_data_from_oracle(SQL_PAGOS)
    print(" LSG")
    db_lsg = fetch_data_from_oracle(SQL_LSG)
    print(" Vendor Bill")
    db_VendorBill = fetch_data_from_oracle(SQL_VENDOR_BILL)

    print("Infor")
    # 6. Infor (SQL Server Infor)
    db_infor = fetch_data_from_sql_trusted(INFOR_SERVER, INFOR_DB, SQL_INFOR)

    print("Extracción de datos finalizada.")

    return {
        "db_Tesoreria": db_Tesoreria,  # NoSerie
        "db_ComprasAri": db_ComprasAri,  # serie
        "db_ComprasDri": db_ComprasDri,  # serie
        "db_Entregas": db_Entregas,  # serie
        "db_autos": db_autos,  # NoSerie
        "db_rac": db_rac,  # NoSerie
        "db_lsg": db_lsg,  # NoSerie
        "db_ControlVtas": db_ControlVtas,  # NumSerie
        "db_ControlVtasLineas": db_ControlVtasLineas,
        "db_payment": db_payment,
        "db_MVAOracle": db_MVAOracle,  # NoSerie
        "db_VendorBill": db_VendorBill,  # NoSerie
        "db_infor": db_infor  # serial
    }


def transform_data(data):
    """Limpia y transforma los DataFrames."""
    print("Iniciando transformación de datos...")

    # --- 1. Limpiar SerialNumber ---
    target_cols = ['NoSerie', 'serie', 'NumSerie', 'serial']
    for name, df in data.items():
        # Buscamos cuál de los nombres de columna existe en este DataFrame, next si busca se detiene.
        col_found = next((c for c in target_cols if c in df.columns), None)
        if col_found:
            df[col_found] = df[col_found].apply(clean_NoSerie)


    # --- 1. Tesorería ---
    db_Tesoreria = limpiar_columnas(data["db_Tesoreria"])

    db_Tesoreria = db_Tesoreria[["mva", "numerodeserie", "origendelrecurso", "fechadeprepagoarrendadora", "fecharecepcionfactura","ligadesoporte"]]
    db_Tesoreria.columns = ["MVA", "NoSerie", "OrigenRecurso", "SheetTesorPrepago", "SheetTesorFactura", "CartaAceptac"]

    db_Tesoreria["SheetTesorPrepago"] = pd.to_datetime(db_Tesoreria["SheetTesorPrepago"], format="%d/%m/%Y",
                                                       errors='coerce')
    db_Tesoreria["SheetTesorFactura"] = pd.to_datetime(db_Tesoreria["SheetTesorFactura"], format="%d/%m/%Y",
                                                       errors='coerce')
    # new records in Jan26
    db_Tesoreria = db_Tesoreria.sort_values(by=["NoSerie", "SheetTesorFactura"],
                                            ascending=[True, False]).reset_index(drop=True)

    #Vacio:False & Lleno:True
    db_Tesoreria["CartaAceptac"] = ~db_Tesoreria["CartaAceptac"].isnull()
    db_Tesoreria["CartaAceptac"] = db_Tesoreria["CartaAceptac"].map({True: "T", False: "F"})
    # It returns True when, we don't have an Invoice...db_Tesoreria['SheetTesorPrepago'].notnull() &
    db_Tesoreria['SheetTesorPropPendiente'] = db_Tesoreria['SheetTesorFactura'].isnull()
    db_Tesoreria['SheetTesorPropPendiente'] = db_Tesoreria['SheetTesorPropPendiente'].map({True: "T", False: "F"})
    # lest create a new df to obtain only status
    db_TesoreriaStatus = db_Tesoreria.copy()
    db_TesoreriaStatus["Id"] = db_TesoreriaStatus.groupby("NoSerie").cumcount() + 1
    db_TesoreriaStatus = db_TesoreriaStatus.query("Id==1").reset_index(drop=True)
    db_TesoreriaStatus = db_TesoreriaStatus[["NoSerie", "CartaAceptac", "SheetTesorPropPendiente"]].copy()

    # --- 2. Contabilidad ---
    db_ComprasAri = limpiar_columnas(data["db_ComprasAri"])
    db_ComprasDri = limpiar_columnas(data["db_ComprasDri"])
    db_Conta = pd.concat([db_ComprasAri.assign(Source="Ariete"), db_ComprasDri.assign(Source="Driven")], axis=0)
    #remove sales and lease back
    db_Conta = db_Conta.query("slb!='TRUE'")
    # Filtramos y reasignamos al mismo dataframe, remove empty serial
    db_Conta = db_Conta[db_Conta['serie'].astype(str).str.len() >= 10]
    db_Conta = (db_Conta
                .groupby(["serie"])
                .agg({"fechafact": "max"})
                .reset_index(drop=False)
                .rename(columns={"serie": "NoSerie", "fechafact": "SheetContaFacDate"})
                )
    db_Conta["SheetContaFacDate"] = pd.to_datetime(db_Conta["SheetContaFacDate"], format='%d/%m/%Y', errors='coerce')

    # ---  Entregas ---
    db_Entregas = limpiar_columnas(data["db_Entregas"])
    db_Entregas = db_Entregas.dropna(subset=["tipodecliente"]).reset_index(drop=True)
    db_Entregas = db_Entregas[['mva', 'serie', 'clientecompletocon', 'tipodecliente']]

    # --- 3. Localización (db_autos) - Ya limpio por query
    db_autos = data["db_autos"].query("IdRank==1").reset_index(drop=True)
    db_autos['LocaFechaPropiedad'] = pd.to_datetime(db_autos['LocaFechaPropiedad'], errors='coerce')

    # --- 4. RAC (db_rac) - Ya limpio por query
    db_rac = data["db_rac"]
    db_rac['MaxCheckIn'] = pd.to_datetime(db_rac['MaxCheckIn'], errors='coerce')

    # --- 5. NetSuite LSG ---
    db_lsg = data["db_lsg"]
    db_lsg["UNegocio"] = db_lsg["UNegocio"].map({5: "LSG", 6: "LSCG"})
    db_lsg = db_lsg.sort_values(by=["NoSerie", "trandate"], ascending=[True, False]).reset_index(drop=True)
    db_lsg["Id"] = db_lsg.groupby("NoSerie").cumcount() + 1
    db_lsg = db_lsg.query("Id==1").reset_index(drop=True)

    # --- 6. NetSuite Pagos Clientes ---
    db_payment = data["db_payment"]
    db_payment = db_payment.sort_values(by=["previousdoc", "trandate", "nextdoc"],
                                        ascending=[True, False, False]).reset_index(drop=True)
    db_payment["Ranking"] = db_payment.groupby('previousdoc').cumcount() + 1
    db_payment_sumary = aggregate_payment_data(db_payment)

    # --- 7. NetSuite MVA ---
    db_MVAOracle = data["db_MVAOracle"]
    db_MVAOracle_processed = preprocess_inventory_data(db_MVAOracle)

    # --- 8. NetSuite Vendor Bill ---
    db_VendorBill = data["db_VendorBill"]
    db_VendorBill = (db_VendorBill
                     .groupby(["NoSerie"])
                     .agg({"trandate": "max"})
                     .reset_index(drop=False)
                     .rename(columns={"trandate": "VendorBillFactDate"})
                     )
    db_VendorBill["VendorBillFactDate"] = pd.to_datetime(db_VendorBill["VendorBillFactDate"], errors='coerce')

    # --- 9. Infor ---
    db_infor = data["db_infor"]
    mapeo_cost_desc = {
        'NA': 'NA', 'compra': 'Compra Inicial', 'compra inicial': 'Compra Inicial',
        'compra inicial con nc wcr88 aplicada': 'Compra Inicial', 'conversion': 'Conversión',
        'devolucion': 'Devolución', 'devolucion venta auto': 'Devolución',
        'intercompañia': 'Intercompañía', 'lease back': 'Lease Back',
        'sale & lease back': 'Lease Back', 'prepago': 'Prepago',
        'prepagos': 'Prepago', 'vencimiento': 'Vencimiento',
        'vencimientos': 'Vencimiento', 'alta de pt para venta': 'Alta PT Venta'
    }
    db_infor = db_infor.sort_values(by=["Uf_Mva", "tag", "acq_date"], ascending=[True, True, True]).reset_index(
        drop=True)
    db_infor["cost_desc"] = db_infor["cost_desc"].fillna("NA").str.lower().map(mapeo_cost_desc)
    db_infor = db_infor.query("cost_desc in ['Prepago','Vencimiento']")
    db_infor = db_infor.groupby(["serial"]).agg({"dispose_date": "max"})
    db_infor = db_infor.reset_index(drop=False)
    db_infor = db_infor.rename(columns={"serial": "NoSerie", "dispose_date": "InforDate"})
    db_infor["InforDate"] = pd.to_datetime(db_infor["InforDate"], errors='coerce')


    # --- 10. Consolidación de Fecha Propiedad (Facturación) ---
    db_FactDate = pd.concat([
        db_VendorBill["NoSerie"],
        db_Tesoreria["NoSerie"],
        db_Conta["NoSerie"],
        db_MVAOracle_processed.dropna(subset=["MaxMVAFacDate"])["NoSerie"],
        db_infor["NoSerie"],
        db_autos["NoSerie"]
    ], axis=0, ignore_index=True).to_frame().drop_duplicates().rename(columns={0: "NoSerie"})

    # print(f"Dimensión Original: {db_FactDate.shape}")
    db_FactDate = pd.merge(db_FactDate, db_VendorBill, on="NoSerie", how="left")
    db_FactDate = pd.merge(db_FactDate, db_Tesoreria[["NoSerie", "OrigenRecurso", "SheetTesorFactura"]],
                           on="NoSerie", how="left")
    db_FactDate = pd.merge(db_FactDate, db_Conta, on="NoSerie", how="left")
    db_FactDate = pd.merge(db_FactDate, db_MVAOracle_processed[["NoSerie", "MaxMVAFacDate"]].rename(
        columns={"MaxMVAFacDate": "MVAFacDate"}), on="NoSerie", how="left")
    db_FactDate = pd.merge(db_FactDate, db_infor, on="NoSerie", how="left")
    db_FactDate = pd.merge(db_FactDate,
                           db_autos[["NoSerie", "LocaFechaPropiedad", "LocaPropiedad", "LocaTipoPropiedad"]],
                           on="NoSerie", how="left")
    db_FactDate = votar_fechas(db_FactDate)

    # --- 11. Fecha de último Ingreso RAC or LSG ---
    db_LastIncome = process_last_income(db_rac, db_lsg)

    #####################################################
    #####################################################
    # --- 12. Consolidación Final (Mesa de Control) ---
    #####################################################
    #####################################################

    print(f"Dimensión Original Mesa Control: {data['db_ControlVtas'].shape}")
    db_MesaControl = data["db_ControlVtas"].copy()
    db_MesaControl['AgnoPromesa'] = pd.to_numeric(db_MesaControl['AgnoPromesa'], errors='coerce')
    db_MesaControl['Creado'] = pd.to_datetime(db_MesaControl['Creado'])
    # Aplicar la función a cada fila y almacenar el resultado en la nueva columna
    db_MesaControl['FechaPromesa'] = db_MesaControl.apply(_determinar_fecha, axis=1)

    # New Add information lines January25
    db_ControlVtasLineas = data["db_ControlVtasLineas"].copy()
    db_ControlVtasLineas = db_ControlVtasLineas.sort_values(by=["IdHeadFac", "class"],
                                                            ascending=[True, True]).reset_index(drop=True)
    db_ControlVtasLineas["Id"] = db_ControlVtasLineas.groupby("IdHeadFac").cumcount() + 1
    db_ControlVtasLineas = db_ControlVtasLineas.query("Id==1").reset_index(drop=True).rename(columns={"class": "Class"})
    db_MesaControl = pd.merge(db_MesaControl,
                              db_ControlVtasLineas[["IdHeadFac", "Class"]],
                              how="left", on=["IdHeadFac"])

    # pagos
    db_MesaControl = pd.merge(db_MesaControl,
                              db_payment_sumary.rename(columns={"previousdoc": "IdHeadFac"}),
                              how="left", on=["IdHeadFac"])

    # fecha de facturara compra
    db_FactDate = db_FactDate[["NoSerie", "FechaFacturaPropiedad", "FuenteFecha", "OrigenRecurso", "LocaPropiedad",
                               "LocaTipoPropiedad"]].rename(columns={"NoSerie": "NumSerie"})
    db_MesaControl = pd.merge(db_MesaControl,
                              db_FactDate, how="left", on=["NumSerie"])

    # last income
    db_LastIncome = db_LastIncome[["NoSerie", "MaxOnRent", "TipoLast"]].rename(columns={"NoSerie": "NumSerie"})
    db_MesaControl = pd.merge(db_MesaControl, db_LastIncome, how="left", on=["NumSerie"])

    # Datos de la Entrega
    db_MesaControl = pd.merge(db_MesaControl,
                              db_Entregas[["serie", "tipodecliente", "clientecompletocon"]].rename(
                                  columns={"serie": "NumSerie", "tipodecliente": "TipoClienteEntrega",
                                           "clientecompletocon": "ClienteCompletoCon"}),
                              how="left", on=["NumSerie"])

    # Status de Tesoreria
    db_MesaControl = pd.merge(db_MesaControl,
                              db_TesoreriaStatus.rename(columns={"NoSerie": "NumSerie"}),
                              how="left", on=["NumSerie"])

    print(f"Dimensión de Mesa de Control final: {db_MesaControl.shape}")
    print("Transformación de datos finalizada.")

    return db_MesaControl, db_FactDate, db_LastIncome, db_payment_sumary


def load_data(df_final, name_schema, name_DB):
    """Carga el DataFrame final a la base de datos de destino."""
    print("Iniciando carga de datos...")
    if df_final.empty:
        print("El DataFrame final está vacío. No se realiza la carga.")
        return False, "DataFrame vacío."

    cgestion = ConnCGestion()
    result_upload, msg_upload = cgestion.upload_DF_SQL(
        df=df_final,
        name_schema=name_schema,
        name_DB=name_DB,
        action="append",
        deleteAllRecords=True
    )
    print(f"Resultado de la carga: {msg_upload}")
    return result_upload, msg_upload


def insert_final_log(pipeline_name, start_time, end_time, status, error_info):
    """
        Inserta un único registro de log con el resultado final del proceso.
        """
    cgestion = ConnCGestion()
    duration = (end_time - start_time).total_seconds()

    # Limitar el mensaje de error para evitar exceder límites si es necesario
    error_message_text = str(error_info)[:8000] if error_info else None

    # Crear el DataFrame para la inserción final
    df_log = pd.DataFrame({
        'PipelineName': [pipeline_name],
        'ExecutionStartDT': [start_time.strftime('%Y-%m-%d %H:%M:%S')],
        'ExecutionEndDT': [end_time.strftime('%Y-%m-%d %H:%M:%S')],
        'Status': [status],
        'DurationSeconds': [round(duration, 2)],
        'ErrorMessage': [error_message_text]
    })
    # Usar upload_DF_SQL para APPEND simple
    result, msg = cgestion.upload_DF_SQL(
        df=df_log, name_schema="dbo",  # Esquema de tu tabla de logs
        name_DB="ETL_Process_Log", action="append",  # Siempre 'append' para logs
        deleteAllRecords=False)
    if result:
        print(f"✅ Log final de '{status}' insertado con éxito en ETL_Process_Log.")
    else:
        print(f"❌ ERROR CRÍTICO: Falló la inserción del log final. Mensaje: {msg}")


def main():
    """Función principal para orquestar la extracción, transformación y carga (ETL)."""
    print("Iniciando proceso ETL...")
    PIPELINE_NAME = "Mesa_Control_Vtas_ETL"
    start_time = dt.datetime.now()
    status = 'SUCCESS'
    error_info = None
    try:
        # 1. Extracción
        raw_data = extract_data()

        # 2. Transformación
        db_MesaControl, db_FactDate, db_LastIncome ,db_payment_sumary= transform_data(raw_data)

        # 3. Carga
        load_data(df_final=db_MesaControl, name_schema="MesaControl", name_DB="ControlVta")
        load_data(df_final=db_FactDate[["NumSerie", "FechaFacturaPropiedad", "FuenteFecha", "OrigenRecurso"]],
                  name_schema="MesaControl", name_DB="FechasFacturas")
        load_data(df_final=db_LastIncome, name_schema="MesaControl", name_DB="LastIncome")
        load_data(df_final=db_payment_sumary, name_schema="MesaControl", name_DB="Payments")


        print("Proceso ETL finalizado exitosamente. 🎉")

    except Exception as e:
        status = 'FAILED'
        # Esto imprimirá el error completo, incluyendo el módulo y la línea
        print("\n" + "=" * 50)
        print("🚨 OCURRIÓ UN ERROR CRÍTICO EN EL PROCESO ETL 🚨")
        print("=" * 50)
        # Aquí usamos traceback.format_exc() para obtener el error completo como un string
        error_info = traceback.format_exc()
        print(error_info)
        # Opcional: imprimir el mensaje de error simple
        print(f"Mensaje del error: {e}")
        print("=" * 50)
    finally:
        end_time = dt.datetime.now()
        duration = (end_time - start_time).total_seconds()
        insert_final_log(PIPELINE_NAME, start_time, end_time, status, error_info)
        if status == 'SUCCESS':
            print("Proceso ETL de datos finalizado exitosamente. 🎉")
        else:
            print("Proceso ETL de datos terminado con FALLA. ❌")


if __name__ == "__main__":
    main()
