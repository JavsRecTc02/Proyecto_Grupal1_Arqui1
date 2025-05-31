
import pygame
from TEA_PROGRAM import tea_program, tea_program2
from PIPELINE_gui import run_pipeline  

# ----------------- Constantes de la interfaz gráfica -----------------
MENU_WIDTH, MENU_HEIGHT = 600, 600
BG_COLOR_MENU       = (0, 0, 0)                
BUTTON_COLOR        = (0, 200, 0)              
BUTTON_HOVER_COLOR  = (0, 150, 0)             
TEXT_COLOR          = (255, 255, 255)         
TITLE_COLOR         = (255, 255, 255)          
FONT_SIZE_TITLE     = 55
FONT_SIZE_BUTTON    = 36
BUTTON_WIDTH        = 200
BUTTON_HEIGHT       = 60
BUTTON_SPACING      = 40  


def draw_button(screen, font, text, rect, mouse_pos):

    x, y, w, h = rect
    if x <= mouse_pos[0] <= x + w and y <= mouse_pos[1] <= y + h:
        color = BUTTON_HOVER_COLOR
    else:
        color = BUTTON_COLOR

    pygame.draw.rect(screen, color, rect, border_radius=8)
    text_surf = font.render(text, True, TEXT_COLOR)
    text_rect = text_surf.get_rect(center=(x + w // 2, y + h // 2))
    screen.blit(text_surf, text_rect)


def main_menu():
    pygame.init()
    screen = pygame.display.set_mode((MENU_WIDTH, MENU_HEIGHT))
    pygame.display.set_caption("TEA Algorithm")

    # Fuentes para título y botones
    title_font = pygame.font.Font(None, FONT_SIZE_TITLE)
    button_font = pygame.font.Font(None, FONT_SIZE_BUTTON)
    clock = pygame.time.Clock()

    # Calculamos posición vertical para centrar ambos botones
    total_buttons_height = 2 * BUTTON_HEIGHT + BUTTON_SPACING
    start_y = (MENU_HEIGHT - total_buttons_height) // 2

    # Coordenadas horizontales centradas
    btn_x = (MENU_WIDTH - BUTTON_WIDTH) // 2
    btn1_y = start_y
    btn2_y = start_y + BUTTON_HEIGHT + BUTTON_SPACING

    encrypt_rect = pygame.Rect(btn_x, btn1_y, BUTTON_WIDTH, BUTTON_HEIGHT)
    decrypt_rect = pygame.Rect(btn_x, btn2_y, BUTTON_WIDTH, BUTTON_HEIGHT)

    # Posición del título
    title_surf = title_font.render("TEA Algorithm", True, TITLE_COLOR)
    title_rect = title_surf.get_rect(center=(MENU_WIDTH // 2, 80))

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Verificamos si clicamos sobre algún botón
                if encrypt_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    run_pipeline(tea_program)
                    return
                elif decrypt_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    run_pipeline(tea_program2)
                    return

        # Dibujado de fondo y componentes
        screen.fill(BG_COLOR_MENU)

        # Dibujamos el título en la parte superior
        screen.blit(title_surf, title_rect)

        # Dibujamos los botones
        draw_button(screen, button_font, "Encriptar", encrypt_rect, mouse_pos)
        draw_button(screen, button_font, "Desencriptar", decrypt_rect, mouse_pos)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main_menu()
