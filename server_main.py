from conexion import conexion_Rummy
import time
import threading

if __name__ == "__main__":
    server = conexion_Rummy()
    server.iniciar_servidor()
    
    time.sleep(1)  # Esperar un momento para que el servidor esté listo
    cliente_host = conexion_Rummy() #Crea una instancia para que el host ingrese

    #Conectar el cliente del host al servidor local
    if cliente_host.conectar_a_servidor('127.0.0.1'):
        print("Host conectado al servidor local")
        try:
            #Mantiene tanto al cliente como al servidor en ejecución
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Cerrando servidor y cliente")
        except Exception as e:
            pass
        finally:
            cliente_host.desconectar()
            server.desconectar()
            print("Servidor y cliente cerrados correctamente")
    
    else:
        print("Error: No se pudo conectar al servidor local")
        server.desconectar()