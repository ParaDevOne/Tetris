# main.py
# Punto de entrada principal del juego Tetris

import sys
import time
import pygame
import logging
import os
from enum import Enum, auto
import traceback

from board import Board
from pieces import PieceGenerator, Piece
from score import ScoreManager
from ui import GameUI
from constants import FPS

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='tetris.log',
    filemode='w'  # Sobreescribir el archivo en cada ejecución
)

# Agregar también logs a la consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)
logging.getLogger().addHandler(console_handler)

# Estados del juego
class GameState(Enum):
    MENU = auto()        # Menú principal
    PLAYING = auto()     # Jugando
    PAUSED = auto()      # Juego en pausa
    GAME_OVER = auto()   # Fin del juego
    RANKINGS = auto()    # Tabla de clasificación
    SETTINGS = auto()    # Configuración

class Game:
    """
    Clase principal que maneja el juego Tetris.
    Coordina la lógica del juego, la interfaz y los eventos.
    """
    
    def __init__(self):
        """
        Inicializa el juego Tetris.
        """
        try:
            # Información del entorno
            logging.info(f"Sistema operativo: {os.name}")
            logging.info(f"Directorio actual: {os.getcwd()}")

            # Inicializar componentes del juego
            self.score_manager = ScoreManager()
            self.ui = GameUI(self.score_manager)

            # Configuración inicial
            self.clock = pygame.time.Clock()
            self.running = True
            self.state = GameState.MENU
            
            # Variables para el manejo de entrada de texto (nombre del jugador)
            self.player_name = ""
            self.input_active = False
            
            # Inicializar componentes específicos del juego
            self._init_game()
            
            # Configurar icono de la ventana
            icon: pygame.Surface = pygame.image.load("./content/images/icon.ico")
            pygame.display.set_icon(icon)

            logging.info("Juego Tetris inicializado correctamente")
        except Exception as e:
            logging.error(f"Error al inicializar el juego: {e}")
            logging.error(traceback.format_exc())
            raise RuntimeError(f"Error al inicializar el juego: {e}")
    
    def _init_game(self):
        """
        Inicializa o reinicia los componentes específicos del juego.
        """
        # Crear tablero nuevo
        self.board = Board()
        
        # Generador de piezas con vista previa configurada
        preview_count = 3  # Valor por defecto
        self.piece_generator = PieceGenerator(int(preview_count))
        
        # Pieza actual
        self.current_piece = self.piece_generator.get_next_piece()
        
        # Velocidad de caída inicial desde configuración
        self.fall_speed = 30  # Valor por defecto
        self.fall_counter = 0
        
        # Activar soft drop (caída rápida)
        self.soft_drop_active = False
        
        # Tiempo para controlar la repetición de teclas
        self.key_repeat_delay = 170  # ms
        self.key_repeat_interval = 50  # ms
        self.last_key_time = 0
        self.last_key = None
        
        # Reiniciar puntuación
        self.score_manager.reset_score()
        
        if hasattr(self, '_game_over_sound_played'):
            self._game_over_sound_played = False
        
        logging.info("Componentes del juego inicializados")
    
    def run(self):
        """
        Ejecuta el bucle principal del juego.
        """
        try:
            logging.info("Iniciando bucle principal del juego")
            
            # Variables para medir rendimiento
            frame_count = 0
            start_time: float = time.time()
            last_fps_log: float = start_time
            
            # Bucle principal
            while self.running:
                # Gestionar eventos
                self._handle_events()
                
                # Actualizar el estado del juego
                self._update()
                
                # Renderizar
                try:
                    self._render()
                except pygame.error as e:
                    logging.error(f"Error de pygame al renderizar: {e}")
                    if "video system not initialized" in str(e):
                        logging.error("El sistema de video se desconectó, intentando reiniciar...")
                        try:
                            pygame.display.quit()
                            pygame.display.init()
                            continue  # Intentar nuevamente en el siguiente frame
                        except:
                            logging.error("No se pudo reiniciar el sistema de video")
                            self.running = False
                            break
                    else:
                        # Otro tipo de error, continuar si es posible
                        logging.warning("Continuando a pesar del error...")
                
                # Incrementar contador de frames
                frame_count += 1
                
                # Registrar FPS cada 5 segundos
                current_time: float = time.time()
                if current_time - last_fps_log > 5:
                    avg_fps: float = frame_count / (current_time - last_fps_log)
                    logging.debug(f"FPS promedio: {avg_fps:.2f}")
                    frame_count = 0
                    last_fps_log: float = current_time
        
        except KeyboardInterrupt:
            logging.info("Juego interrumpido manualmente")
        except Exception as e:
            logging.error(f"Error en el bucle principal: {e}")
            logging.error(traceback.format_exc())
            raise
        finally:
            # Guardar puntuaciones antes de salir
            self.score_manager.save_highscores()
            
            # Limpiar recursos de pygame
            logging.info("Cerrando pygame y liberando recursos...")
            try:
                pygame.display.quit()
                pygame.quit()
            except Exception as e:
                logging.warning(f"Error al cerrar pygame: {e}")
            
            logging.info("Juego terminado")
    
    def _handle_events(self):
        """
        Maneja los eventos de entrada del usuario.
        """
        for event in pygame.event.get():
            # Evento de cierre de ventana
            if event.type == pygame.QUIT:
                self.running = False
                return
            
            # Manejar eventos según el estado actual
            if self.state == GameState.MENU:
                self._handle_menu_events(event)
            elif self.state == GameState.PLAYING:
                self._handle_game_events(event)
            elif self.state == GameState.PAUSED:
                self._handle_pause_events(event)
            elif self.state == GameState.GAME_OVER:
                self._handle_game_over_events(event)
            elif self.state == GameState.RANKINGS:
                self._handle_rankings_events(event)
            elif self.state == GameState.SETTINGS:
                self._handle_settings_events(event)
    
    def _handle_menu_events(self, event):
        """
        Maneja los eventos en el menú principal.
        
        Args:
            event (pygame.event.Event): Evento a manejar
        """
        action = self.ui.handle_menu_input(event, self.ui.menu_options["main"])
        if action == "Jugar":
            self._init_game()
            self.state = GameState.PLAYING
        elif action == "Rankings":
            self.ui.selected_option = 0
            self.state = GameState.RANKINGS
        elif action == "Configuración":
            self.ui.selected_option = 0
            self.state = GameState.SETTINGS
        elif action == "Salir":
            self.running = False
    
    def _handle_game_events(self, event):
        """
        Maneja los eventos durante el juego.
        
        Args:
            event (pygame.event.Event): Evento a manejar
        """
        if event.type == pygame.KEYDOWN:
            # Controles fijos
            pause_key = pygame.K_p
            exit_key = pygame.K_ESCAPE
            hard_drop_key = pygame.K_SPACE
            move_down_key = pygame.K_DOWN

            # Pausa
            if event.key == pause_key:
                self.state = GameState.PAUSED
                self.ui.selected_option = 0
                return
            elif event.key == exit_key:
                self.state = GameState.MENU
                self.ui.selected_option = 0
                return
            elif event.key == hard_drop_key:
                self._perform_hard_drop()
                return
            elif event.key == move_down_key:
                self.soft_drop_active = True

            self.last_key = event.key
            self.last_key_time: int = pygame.time.get_ticks()
            self._apply_key_movement(event.key)
        elif event.type == pygame.KEYUP:
            move_down_key = pygame.K_DOWN
            if event.key == move_down_key:
                self.soft_drop_active = False
            if event.key == self.last_key:
                self.last_key = None
    
    def _handle_pause_events(self, event):
        """
        Maneja los eventos en el menú de pausa.
        
        Args:
            event (pygame.event.Event): Evento a manejar
        """
        action = self.ui.handle_menu_input(event, self.ui.menu_options["pause"])
        if action == "Continuar":
            self.state = GameState.PLAYING
        elif action == "Reiniciar":
            self._init_game()
            self.state = GameState.PLAYING
        elif action == "Salir al Menú":
            self.state = GameState.MENU
            self.ui.selected_option = 0
    
    def _handle_game_over_events(self, event):
        """
        Maneja los eventos en la pantalla de game over.
        
        Args:
            event (pygame.event.Event): Evento a manejar
        """
        # Verificar si es récord
        if self.score_manager.is_highscore():
            # Entrada de texto para nombre del jugador
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    # Guardar puntuación
                    self.score_manager.add_highscore(
                        self.player_name if self.player_name else "Anónimo",
                        level=self.board.level,
                        lines=self.board.lines_cleared
                    )
                    # Volver al menú
                    self.state = GameState.MENU
                    self.ui.selected_option = 0
                    self.player_name = ""
                elif event.key == pygame.K_BACKSPACE:
                    # Borrar último carácter
                    self.player_name = self.player_name[:-1]
                elif len(self.player_name) < 15:  # Limitar longitud
                    # Añadir carácter
                    if event.unicode.isalnum() or event.unicode in " -_":
                        self.player_name += event.unicode

    
    def _handle_rankings_events(self, event):
        """
        Maneja los eventos en la pantalla de rankings.
        
        Args:
            event (pygame.event.Event): Evento a manejar
        """
        if event.type == pygame.KEYDOWN:
            exit_key = pygame.K_ESCAPE
            if event.key == exit_key:
                self.state = GameState.MENU
                self.ui.selected_option = 0

    def _handle_settings_events(self, event):
        """
        Maneja los eventos en la pantalla de configuración.
        
        Args:
            event (pygame.event.Event): Evento a manejar
        """
        # Ya no hay configuración, volver al menú
        self.state = GameState.MENU
        self.ui.selected_option = 0
    
    def _update(self):
        """
        Actualiza el estado del juego según el estado actual.
        """
        if self.state == GameState.PLAYING:
            self._update_game()
    
    def _update_game(self):
        """
        Actualiza el estado del juego durante el gameplay.
        """
        current_time: int = pygame.time.get_ticks()
        
        # Manejar repetición de teclas
        if self.last_key and current_time - self.last_key_time > self.key_repeat_delay:
            # Aplicar movimiento repetido
            self._apply_key_movement(self.last_key)
            # Actualizar tiempo con intervalo de repetición
            self.last_key_time = current_time - (self.key_repeat_interval - self.key_repeat_delay)
        
        # Valores fijos para la velocidad
        fall_speed_decrement = 1
        min_fall_speed = 5
        initial_fall_speed = 30
        level_fall_speed: int = max(
            int(min_fall_speed),
            int(initial_fall_speed) - (self.board.level - 1) * int(fall_speed_decrement)
        )
        
        # Aplicar soft drop (caída rápida)
        fall_speed: int = level_fall_speed // 4 if self.soft_drop_active else level_fall_speed
        
        # Incrementar contador
        self.fall_counter += 1
        
        # Verificar si es momento de mover la pieza hacia abajo
        if self.fall_counter >= fall_speed:
            # Intentar mover hacia abajo
            self._move_piece_down()
            
            # Reiniciar contador
            self.fall_counter = 0

    def _apply_key_movement(self, key):
        """
        Aplica el movimiento según la tecla presionada.
        
        Args:
            key (int): Código de la tecla presionada
        """
        # Controles fijos
        move_left = pygame.K_LEFT
        move_right = pygame.K_RIGHT
        rotate = pygame.K_UP
        
        # Guardar posición anterior para comprobar colisiones
        original_x = self.current_piece.x
        original_y = self.current_piece.y
        original_rotation = self.current_piece.rotation
        
        # Mover según la tecla
        if key == move_left:
            self.current_piece.move_left()
        elif key == move_right:
            self.current_piece.move_right()
        elif key == rotate:
            self.current_piece.rotate()
        
        # Verificar colisiones
        if not self.board.is_valid_position(self.current_piece):
            # Restaurar posición si hay colisión
            self.current_piece.x = original_x
            self.current_piece.y = original_y
            if key == rotate:
                self.current_piece.rotation = original_rotation
    
    def _move_piece_down(self):
        """
        Mueve la pieza actual hacia abajo.
        Si no puede moverse, fija la pieza al tablero y genera una nueva.
        """
        # Guardar posición anterior
        original_y = self.current_piece.y
        
        # Mover hacia abajo
        self.current_piece.move_down()
        
        # Verificar colisión
        if not self.board.is_valid_position(self.current_piece):
            # Restaurar posición
            self.current_piece.y = original_y
            
            # Fijar pieza al tablero
            if not self.board.add_piece(self.current_piece):
                # Game over si no se puede fijar la pieza
                self.state = GameState.GAME_OVER
                logging.info(f"Game Over - Puntuación: {self.score_manager.get_current_score()}")
                return
            
            # Generar nueva pieza
            self.current_piece = self.piece_generator.get_next_piece()
            
            # Verificar si la nueva pieza puede ser colocada
            if not self.board.is_valid_position(self.current_piece):
                # Game over si no hay espacio para la nueva pieza
                self.state = GameState.GAME_OVER
                logging.info(f"Game Over - Puntuación: {self.score_manager.get_current_score()}")
    
    def _perform_hard_drop(self):
        """
        Realiza un hard drop (caída instantánea) de la pieza actual.
        """
        # Calcular la distancia que caerá la pieza
        distance = self.board.hard_drop(self.current_piece)

        # Fijar pieza al tablero
        if not self.board.add_piece(self.current_piece):
            # Game over si no se puede fijar la pieza
            self.state = GameState.GAME_OVER
            logging.info(f"Game Over - Puntuación: {self.score_manager.get_current_score()}")
            return
            
        # Generar nueva pieza
        self.current_piece = self.piece_generator.get_next_piece()
        
        # Verificar si la nueva pieza puede ser colocada
        if not self.board.is_valid_position(self.current_piece):
            # Game over si no hay espacio para la nueva pieza
            self.state = GameState.GAME_OVER
            logging.info(f"Game Over - Puntuación: {self.score_manager.get_current_score()}")
    
    def _render(self):
        """
        Renderiza el juego en pantalla según el estado actual.
        """
        # Renderizar según el estado del juego
        if self.state == GameState.MENU:
            self.ui.draw_main_menu()
        elif self.state == GameState.PLAYING:
            self._render_game()
        elif self.state == GameState.PAUSED:
            self._render_game()  # Renderizar juego en el fondo
            self.ui.draw_pause_menu()
        elif self.state == GameState.GAME_OVER:
            self._render_game()  # Renderizar juego en el fondo
            self.ui.draw_game_over(
                self.score_manager.get_current_score(),
                self.board.level,
                self.board.lines_cleared
            )
            
            # Mostrar entrada de texto si es récord
            if self.score_manager.is_highscore():
                # Obtener dimensiones de ventana desde configuración
                window_width = 800
                window_height = 600
                
                # Fondo para texto
                text_bg_rect = pygame.Rect(
                    window_width // 4,
                    window_height // 2 + 100,
                    window_width // 2,
                    40
                )
                pygame.draw.rect(self.ui.window, (50, 50, 50), text_bg_rect)
                pygame.draw.rect(self.ui.window, (100, 100, 100), text_bg_rect, 2)
                
                # Mostrar texto de entrada
                name_text: str = f"Nombre: {self.player_name}"
                if pygame.time.get_ticks() % 1000 < 500:
                    name_text += "|"  # Cursor parpadeante
                self.ui.draw_text(
                    name_text,
                    self.ui.medium_font,
                    (255, 255, 255),
                    window_width // 2,
                    window_height // 2 + 120,
                    center=True
                )
                
        elif self.state == GameState.RANKINGS:
            self.ui.draw_rankings()
        elif self.state == GameState.SETTINGS:
            pass  # Ya no hay config_ui
        
        # Actualizar pantalla
        pygame.display.flip()
    
    def _render_game(self):
        """
        Renderiza el estado actual del juego.
        """
        # Dibujar fondo
        self.ui.draw_background()
        
        # Dibujar tablero
        self.ui.draw_board(self.board)
        
        # Dibujar pieza actual
        self.ui.draw_piece(self.current_piece)
        
        # Dibujar próximas piezas
        self.ui.draw_next_pieces(self.piece_generator.peek_next_pieces())
        
        # Dibujar panel de puntuación
        self.ui.draw_score_panel(
            self.score_manager.get_current_score(),
            self.board.level,
            self.board.lines_cleared,
            self.score_manager.get_highscore()
        )


# Punto de entrada principal
if __name__ == "__main__":
    try:
        # Configurar driver de video según el sistema operativo
        drivers: list[str] = []
        driver_set = False

        if os.name == 'nt':
            # Windows
            drivers = ['windows']
        elif sys.platform.startswith("linux"):
            # Linux
            drivers = ['wayland', 'x11', 'fbcon', 'directfb', 'svgalib']
        elif sys.platform == "darwin":
            # macOS
            drivers = ['cocoa']

        for driver in drivers:
            try:
                os.environ["SDL_VIDEODRIVER"] = driver
                pygame.display.init()
                logging.info(f"Driver de video '{driver}' inicializado correctamente")
                driver_set = True
                break
            except pygame.error:
                logging.warning(f"No se pudo inicializar el driver '{driver}'")
                pygame.display.quit()

        if not driver_set:
            logging.error("No se pudo inicializar ningún driver de video")
            sys.exit(1)

        # Configuración de DPI para Windows
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                logging.warning("No se pudo configurar DPI awareness")

        # Mostrar información de versiones
        logging.info(f"Python versión: {sys.version}")
        logging.info(f"Pygame versión: {pygame.version.ver}")
        logging.info(f"SDL versión: {pygame.version.SDL}")
        
        # Inicializar pygame de forma básica
        pygame.init()
        
        # Crear instancia del juego y ejecutar
        game = Game()
        game.run()
        
    except Exception as e:
        logging.error(f"Error fatal: {e}")
        logging.error(traceback.format_exc())
        
        # Asegurar que pygame se cierra correctamente
        try:
            pygame.quit()
        except:
            pass
            
        # Mostrar mensaje de error también en consola
        print(f"Error fatal: {e}")
        print("Revisa el archivo tetris.log para más detalles")
        
        sys.exit(1)

