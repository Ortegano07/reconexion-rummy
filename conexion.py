import socket
import threading
import json
import time

class conexion_Rummy:
    def __init__(self):
        self.puerto = 5555
        self.ejecutandose = False
        self.candado = threading.RLock()

        # Host
        self.socket_servidor = None
        self.clientes = []
        self.cola_mensajes = []
        self.estado_juego = None
        self.nombre_partida = None
        self.id_jugador_enviador = None  # Atributo para el ID del jugador que envía mensajes

        # Cliente
        self.socket_cliente = None
        self.conectado = False
        self.id_jugador = None
        self.hilo_recepcion = None
        self.conexiones_disponibles = []
        self.jugadores_desconectados = {}  # Nuevo: almacena datos de jugadores desconectados

        # eventos 
        self.eventos_conexion = []

    #----------------------
    # En caso de ser el Host
    #----------------------

    def iniciar_servidor(self):
        self.socket_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_servidor.bind(('0.0.0.0', self.puerto))
        self.socket_servidor.listen(7)
        self.ejecutandose = True
        self.nombre_partida = input("Ingrese el nombre de la partida: ")
        hilo_servidor = threading.Thread(target=self.aceptar_conexiones)
        hilo_servidor.daemon = True
        hilo_servidor.start()

        hilo_anuncio = threading.Thread(target=self.anunciar_servidor)
        hilo_anuncio.daemon = True
        hilo_anuncio.start()

        hilo_procesar = threading.Thread(target=self._procesar_mensajes)
        hilo_procesar.daemon = True
        hilo_procesar.start()


        print(f"Servidor iniciado en el puerto {self.puerto}, esperando jugadores...")
    
    def aceptar_conexiones(self):
        while self.ejecutandose:
            try:
                socket_cliente, addr = self.socket_servidor.accept()
                with self.candado:
                    print(f"Cliente conectado desde {addr}")
                    id_jugador = len(self.clientes) 
                    # Añadir el cliente a la lista
                    manejador_cliente = threading.Thread(target=self._manejar_cliente, args=(socket_cliente, id_jugador))
                    manejador_cliente.daemon = True
                    manejador_cliente.start()

                    self.clientes.append({
                        'socket': socket_cliente,
                        'id': id_jugador,
                        'thread': manejador_cliente
                    })
                    
                    # Notificar evento de nueva conexión
                    self.enviar_a_cliente(id_jugador,{
                        'type': 'Bienvenido',
                        'id_jugador': id_jugador,
                        'game_state': self.estado_juego
                    })
                    # Notificar a todos
                    self.difundir({
                        'type': 'NuevoJugador',
                        'id_jugador': id_jugador,
                        'TotalJugadores': len(self.clientes)
                    })
                print(f"Nuevo jugador conectado: ID {id_jugador}, Total jugadores: {len(self.clientes)}")
            except Exception as e:
                if self.ejecutandose:
                    print(f"Error al aceptar conexiones: {e}")
    
    def _manejar_cliente(self, socket_cliente, id_jugador):
        try:
            while self.ejecutandose:
                data = socket_cliente.recv(4096)
                if not data:
                    break

                mensaje = json.loads(data.decode('utf-8'))
                with self.candado:
                    self.cola_mensajes.append((id_jugador, mensaje))
                    
                    if mensaje.get('type') == 'ClienteDesconectado':
                        print(f"Mensaje del cliente: {mensaje}")
                        # Guardar datos del jugador desconectado
                        self.jugadores_desconectados[id_jugador] = {
                            'estado_juego': self.estado_juego,
                            'nombre': mensaje.get('nombre', f'Jugador{id_jugador}')
                        }
                        self.difundir({
                            'type': 'JugadorDesconectado',
                            'id_jugador': id_jugador,
                            'TotalJugadores': len(self.clientes)
                        })
                        self._eliminar_cliente(id_jugador)
                        break
                    elif mensaje.get('type') == 'Reconectar':
                        # Procesar reconexión
                        datos_guardados = self.jugadores_desconectados.get(id_jugador)
                        if datos_guardados:
                            self.enviar_a_cliente(id_jugador, {
                                'type': 'Reconectado',
                                'id_jugador': id_jugador,
                                'estado_juego': datos_guardados['estado_juego'],
                                'nombre': datos_guardados['nombre']
                            })
                            self.difundir({
                                'type': 'JugadorReconectado',
                                'id_jugador': id_jugador,
                                'nombre': datos_guardados['nombre']
                            })
                            del self.jugadores_desconectados[id_jugador]
        except (ConnectionResetError, socket.error) as e:
            print(f"Error con el cliente {id_jugador}: Conexión perdida - {e}")
        finally:
            self._eliminar_cliente(id_jugador)

    def _enviar_mensajes(self,id_jugador_origen,mensaje):
        print("Mensaje de parte de{id_jugador_origen}:{mensaje}")

        if mensaje.get('type') == 'chat_message':
            # Añadir información sobre el remitente
            mensaje['sender_id'] = id_jugador_origen
            # Reenviar el mensaje a todos los demás clientes
            self.difundir(mensaje)

    def _eliminar_cliente(self, id_jugador):
        with self.candado:
            clientes_a_eliminar = [c for c in self.clientes if c['id'] == id_jugador]
            for cliente in clientes_a_eliminar:
                try:
                    cliente['socket'].shutdown(socket.SHUT_RDWR)
                    cliente['socket'].close()
                except Exception as e:
                    print(f"Error cerrando socket de cliente {id_jugador}: {e}")
            # Elimina fuera del bucle
            self.clientes = [c for c in self.clientes if c['id'] != id_jugador]
            self.difundir({
                'type': 'JugadorDesconectado',
                'id_jugador': id_jugador,
                'TotalJugadores': len(self.clientes)
            })

    def difundir(self, mensaje):
        for cliente in self.clientes:
            if cliente['id'] != mensaje.get('id_jugador'):
                try: 
                    cliente['socket'].send((json.dumps(mensaje) + '\n').encode('utf-8'))
                except Exception as e:
                    print(f"Error al enviar mensaje al cliente {cliente['id']}: {e}")
            

    def enviar_a_cliente(self, id_jugador, mensaje):
        for cliente in self.clientes:
            if cliente['id'] == id_jugador:
                try:
                    cliente['socket'].sendall((json.dumps(mensaje) + '\n').encode('utf-8'))
                except Exception as e:
                    print(f"Error al enviar mensaje al cliente {id_jugador}: {e}")
    def anunciar_servidor(self):
        socket_anuncio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_anuncio.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        socket_anuncio.settimeout(1)

        mensaje = json.dumps({
            'type': 'RummyServer',
            'port': self.puerto,
            'partida': self.nombre_partida
        }).encode('utf-8')
        try:
            while self.ejecutandose:
                socket_anuncio.sendto(mensaje, ('255.255.255.255', 5556)) # Puerto diferente al de conexión
                time.sleep(5) # Anunciarse cada 5 segundos
        except Exception as e:
            print(f"Error en el anuncio del servidor: {e}")
        finally:
            socket_anuncio.close()      

    def _procesar_mensajes(self):
        while self.ejecutandose:
            id_jugador = None
            mensaje = None
            with self.candado:
                if self.cola_mensajes:
                    id_jugador, mensaje = self.cola_mensajes.pop(0)
            if mensaje is not None:
                # Manejar el mensaje aquí
                if mensaje.get('type') == 'NuevoJugador':
                    print(f"Nuevo jugador conectado: ID {mensaje['id_jugador']}, Total jugadores: {mensaje['TotalJugadores']}")
            


    #----------------------
    # En caso de ser Cliente
    #----------------------

    def conectar_a_servidor(self, ip_servidor, id_jugador_reconectar=None):
        try:
            self.socket_cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_cliente.connect((ip_servidor, self.puerto))
            self.conectado = True
            self.hilo_recepcion = threading.Thread(target=self._recibir_mensajes)
            self.hilo_recepcion.daemon = True
            self.hilo_recepcion.start()

            # Si es reconexión, enviar mensaje especial
            if id_jugador_reconectar is not None:
                mensaje_reconectar = {
                    'type': 'Reconectar',
                    'id_jugador': id_jugador_reconectar
                }
                self.socket_cliente.sendall((json.dumps(mensaje_reconectar) + '\n').encode('utf-8'))

            return True
        except Exception as e:
            print(f"Error al conectar al servidor: {e}")
            return False
        
    def _recibir_mensajes(self):
        buffer = ""
        while self.conectado:
            try:
                data = self.socket_cliente.recv(4096)
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    mensaje_str, buffer = buffer.split('\n', 1)
                    if mensaje_str.strip():
                        mensaje = json.loads(mensaje_str)
                        self._manejo_mensaje_red(mensaje)
                        
            except Exception as e:
                print(f"Error al recibir mensaje del servidor: {e}")
                self.conectado = False
                # Intentar reconexión automática
                if self.id_jugador is not None and self.socket_cliente is not None:
                    ip_servidor = self.socket_cliente.getpeername()[0]
                    self.intentar_reconexion(ip_servidor)
                break
    
    def _manejo_mensaje_red(self, mensaje):
        if mensaje['type'] == 'Bienvenido':
            self.id_jugador = mensaje['id_jugador']
            print(self.id_jugador)
            self.estado_juego = mensaje.get('game_state', None)
        elif mensaje['type'] == 'Reconectado':
            self.id_jugador = mensaje['id_jugador']
            self.estado_juego = mensaje.get('estado_juego', None)
            print(f"Reconectado como {mensaje.get('nombre')}, estado restaurado.")
        elif mensaje['type'] == 'JugadorReconectado':
            print(f"Jugador {mensaje['nombre']} (ID {mensaje['id_jugador']}) se ha reconectado.")
        elif mensaje['type'] == 'game_update':
            self.estado_juego = mensaje.get('game_state', None)
        elif mensaje['type'] == 'NuevoJugador':
            print(f"Nuevo jugador conectado: ID {mensaje['id_jugador']}, Total jugadores: {mensaje['TotalJugadores']}")
        elif mensaje['type'] == 'JugadorDesconectado':
            print(f"Jugador desconectado: ID {mensaje['id_jugador']}, Total jugadores: {mensaje['TotalJugadores']}")
        elif mensaje['type'] == 'ServidorCerrado':
            print("El servidor ha cerrado la conexión.")
            self.desconectar()
    def desconectar(self):# Cierra todas las conexiones
        self.ejecutandose = False
        self.conectado = False
        # Cerrar servidor
        if self.socket_servidor:
            try:
                self.difundir({
                    'type': 'ServidorCerrado'
                })
            except Exception as e:
                print(f"Error al notificar a cliente sobre el cierre del servidor: {e}")
            self.socket_servidor.close()
            self.socket_servidor = None

        # Cerrar cliente (y notificar al servidor)
        if self.socket_cliente and self.id_jugador is not None:
            try:
                mensaje_desconexion = {
                    'type': 'ClienteDesconectado',
                    'id_jugador': self.id_jugador
                }
                self.socket_cliente.send(json.dumps(mensaje_desconexion).encode('utf-8'))
                time.sleep(0.5)
            except Exception as e:
                print(f"Error al notificar al servidor sobre la desconexión: {e}")
            finally:
                try:
                    self.socket_cliente.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.socket_cliente.close()
                self.socket_cliente = None
                self._manejo_mensaje_red({
                    'type': 'JugadorDesconectado',
                    'id_jugador': self.id_jugador,
                    'TotalJugadores': len(self.clientes)
                })
        else:
            print("Socket cliente no existe o ID de jugador no asignado")
            print(f"Socket cliente: {self.socket_cliente}, ID jugador: {self.id_jugador}")

        # Cerrar hilo de recepción del cliente
        if self.hilo_recepcion and threading.current_thread() != self.hilo_recepcion:
            self.hilo_recepcion.join()
        
    def encontrar_ip_servidor(self):
        socket_busqueda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_busqueda.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socket_busqueda.bind(('', 5556)) # Escuchar en el mismo puerto que el anuncio
        socket_busqueda.settimeout(5) # Esperar 5 segundos

        print("Buscando servidor en la red...")
        try:
            while True:
                data, direccion_servidor = socket_busqueda.recvfrom(1024)
                mensaje = json.loads(data.decode('utf-8'))
                ip_encontrada = direccion_servidor[0]
                server_completo = []
                if mensaje.get('type') == 'RummyServer' and direccion_servidor[0] not in self.conexiones_disponibles:
                    nombre_partida = mensaje.get('partida', 'Desconocida')
                    print(f"Servidor encontrado en la IP: {ip_encontrada} - Partida: {nombre_partida}")
                    self.conexiones_disponibles.append(ip_encontrada)
                    server_completo.append((ip_encontrada, nombre_partida))
                    print(f"Conexiones disponibles: {self.conexiones_disponibles}")
                else:
                    break
        except socket.timeout:
            if not self.conexiones_disponibles:
                print("Tiempo de búsqueda agotado. Servidor no encontrado.")
            else:
                print("Búsqueda finalizada.")
        except Exception as e:
            print(f"Error buscando servidor: {e}")
        finally:
            socket_busqueda.close()
        return self.conexiones_disponibles if self.conexiones_disponibles else None
    
    def intentar_reconexion(self, ip_servidor, intentos=5, espera=3):
        """
        Intenta reconectar automáticamente al servidor usando el id_jugador anterior.
        """
        for intento in range(intentos):
            print(f"Intentando reconectar... (Intento {intento + 1}/{intentos})")
            exito = self.conectar_a_servidor(ip_servidor, id_jugador_reconectar=self.id_jugador)
            if exito:
                print("Reconexión exitosa.")
                return True
            time.sleep(espera)
        print("No se pudo reconectar después de varios intentos.")
        return False