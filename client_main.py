from conexion import conexion_Rummy
import time

if __name__ == "__main__":
    client = conexion_Rummy()
    servidores_encontrados = client.encontrar_ip_servidor()
    print(f"Servidores encontrados: {servidores_encontrados}")

    if servidores_encontrados and client.conectar_a_servidor(servidores_encontrados[0]): 
        print(f"Cliente conectado al servidor en {servidores_encontrados[0]}")
        try:
            # Mantiene al cliente funcionando y verifica reconexión
            while True:
                if not client.conectado:
                    print("Desconectado del servidor. Intentando reconectar...")
                    reconectado = client.intentar_reconexion(servidores_encontrados[0])
                    if not reconectado:
                        print("No se pudo reconectar. Saliendo...")
                        break
                time.sleep(1)
        except KeyboardInterrupt:
            print("Cliente desconectándose...")
        finally:
            client.desconectar()
    else:
        print("Fallo al conectar con el servidor.")