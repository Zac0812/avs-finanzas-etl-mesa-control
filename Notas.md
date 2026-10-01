Librerias instaladas en la terminal de pycharm

pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

adicional debemos instalar

pip install python-dotenv


TODO cuando se implemente en otra PC

- En .env `PATH_CREDS_DRIVE` debe ser cambiada, al path correspondiente en la maquina donde este la tarea programada













---------------------
Este es un proyecto que fue desarrollado en Python para realizar un ETL y resguardar datos en una tabla de sql server. Necesito que me apoyes a revisar una incosistencia que esta teniendo el proceso actualmente. Para esto deberas:

1. No modificar ningún documento del directorio, actual, dado que es el reporte productivo. Puedes leerlo y usarlo, sin embargo  no modificar.
2. Si necesitas crear algo crea una carpeta dedicada, dado que no debe convinarse con el proyecto actual.
3. Vamos a revisar principalmente el documento de `C:\Users\luis.meza\PycharmProjects\MesaControl\main.py`
4. Podriamos trabajar con el Env de pycharm o si lo prefieres creo tener todas las librerías en EnvVisual
6. El error es que la tabla MesaControl.ControlVta tiene un registro duplicado que es el IdSalesCar=136214, necesitamos identificar de donde viene ese dato duplicado para poder comentar a los responsables del proceso

Por lo anterior ayúdame a buscar el origen de dicho dato duplicado


---------------------

Este es un proyecto que fue desarrollado en Python para realizar un ETL y resguardar datos en una tabla de sql server. Necesito que me apoyes a revisar unas situaciones

1. No modificar ningún documento del directorio, actual, dado que es el reporte productivo. Puedes leerlo y usarlo, sin embargo  no modificar.
2. Si necesitas crear algo, crea una carpeta dedicada, dado que no debe convinarse con el proyecto actual.
3. Vamos a revisar principalmente el documento de `C:\Users\luis.meza\PycharmProjects\MesaControl\sync_payments_json.py`
4. Podriamos trabajar con el Env de pycharm o si lo prefieres puedes usar en el Env llamado EnvVisual
5. Lo que no se es que hace `C:\Users\luis.meza\PycharmProjects\MesaControl\sync_payments_json.py` ni como se relacioana con el proyecto según yo por algo se creo pero no se que es.
   




Este es un proyecto que fue desarrollado en Python para realizar un ETL y resguardar datos en una tabla de sql server. Necesito que me apoyes respecto a su documentación y su respectivo almacenamiento en git para esto.

1. No modificar código alguno del proyecto, lo que vamos hacer es crear cosas nuevas y su reordenamiento para su mejor compresión.
2. Crear un carpeta en el proyecto algo que haga referencia a codigos de prueba o test, ahí vas almacenar a `C:\Users\luis.meza\PycharmProjects\MesaControl\sync_payments_json.py`
3. Crear el gitignore,  proponme que debemos y que no guardar, importante segurameten las variables de `C:\Users\luis.meza\PycharmProjects\MesaControl\.env` no se van a subir a git pero entonces necesito que me crees un documento algo como .env_test o algo similar con las variables necesarias para que sepan que es necesario tener el documento de .env lo mismo para `C:\Users\luis.meza\PycharmProjects\MesaControl\credentials` entonces deberia haber alg como `credential_test`  con un ejemplo de los .json necesario para su respectivo uso
4. `Notas.md` se debe guardar dado que son notas personas
5. Deberia existir el requeriments para poder instalarlo en otra pc lo necesario para poder corre el proyecto
6. Los codigos principales como data_processing,data_soruce, main, mainOthers preferiria no ponerlos en una subcarpeta creo que estan bien así en la raiz
7. Creame un REDME que explique el proyecto en general lo que queremos ejecutar en un .bat que tenga algo como cd C:\Users\Luis.Meza\Desktop\Python Projects\MesaControl
python main.py
python mainOthers.py
8. No ejecutes nada de git solo hazme la propueta del gitignore
