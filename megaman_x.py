# megaman_x.py
import pygame
import os
import sys
import numpy as np
import wave
import struct

# --------------------
# Inicialização
# --------------------
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
try:
    pygame.mixer.init()
except Exception:
    # Se algo falhar com mixer, seguiremos sem som
    print("[AVISO] mixer do pygame não pôde ser inicializado. Sem som.")

# --------------------
# Configurações
# --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets", "megamanx")

LARGURA, ALTURA = 800, 400
TELA = pygame.display.set_mode((LARGURA, ALTURA))
pygame.display.set_caption("Mega Man X - Demo")
FPS = 60
CHAO = ALTURA - 80
GRAVIDADE = 0.9
WHITE = (255, 255, 255)
BG = (30, 120, 255)
FLOOR_COLOR = (100, 60, 20)

# Se seus sprites originais apontam para a direita, mantenha "right".
# Se apontam para a esquerda, mude para "left".
SOURCE_FACING = "right"

# --------------------
# Utilitários: carregar sprites
# --------------------
def carregar_sprites_try(caminho_base):
    """
    Tento carregar primeiro a pasta *_cortado se existir, senão a original.
    Retorna lista de surfaces (pode ser vazia).
    """
    opc1 = caminho_base + "_cortado"
    opc2 = caminho_base
    for caminho in (opc1, opc2):
        if os.path.exists(caminho) and os.path.isdir(caminho):
            frames = []
            for arq in sorted(os.listdir(caminho)):
                if arq.lower().endswith(".png"):
                    try:
                        img = pygame.image.load(os.path.join(caminho, arq)).convert_alpha()
                        frames.append(img)
                    except Exception as e:
                        print(f"[ERRO] Falha ao carregar {arq}: {e}")
            if frames:
                print(f"✅ Carregados {len(frames)} frames de: {os.path.relpath(caminho)}")
                return frames
    print(f"[AVISO] Nenhum frame em {os.path.relpath(caminho_base)} (busquei _cortado e original).")
    return []

# --------------------
# Função para gerar sons simples (8-bit-ish) caso faltarem
# --------------------
def gerar_som_local(nome, freq=880, dur=0.12, tipo="quadrada"):
    os.makedirs(os.path.join(BASE_DIR, "assets", "sounds"), exist_ok=True)
    caminho = os.path.join(BASE_DIR, "assets", "sounds", f"{nome}.wav")
    if os.path.exists(caminho):
        return caminho
    taxa = 44100
    t = np.linspace(0, dur, int(taxa * dur), False)
    if tipo == "quadrada":
        onda = 0.5 * np.sign(np.sin(2 * np.pi * freq * t))
    else:
        onda = 0.5 * np.sin(2 * np.pi * freq * t)
    onda = np.int16(onda * 32767)
    with wave.open(caminho, "w") as f:
        f.setparams((1, 2, taxa, 0, "NONE", "not compressed"))
        for s in onda:
            f.writeframes(struct.pack("h", s))
    print(f"[OK] Som gerado: {caminho}")
    return caminho

# gerar sons (se já existirem, retornarão o arquivo existente)
SOM_ATIRAR = gerar_som_local("x_shoot", 1100, 0.09, "quadrada")
SOM_PULO = gerar_som_local("x_jump", 520, 0.18, "senoide")
SOM_CORRIDA = gerar_som_local("x_run", 140, 0.04, "quadrada")

# carrega objetos Sound (se mixer disponível)
def carregar_som_ou_none(caminho):
    try:
        return pygame.mixer.Sound(caminho)
    except Exception:
        return None

SOUND_SHOOT = carregar_som_ou_none(SOM_ATIRAR)
SOUND_JUMP = carregar_som_ou_none(SOM_PULO)
SOUND_RUN = carregar_som_ou_none(SOM_CORRIDA)

# --------------------
# Classes do jogo
# --------------------
class Tiro(pygame.sprite.Sprite):
    def __init__(self, x, y, direcao):
        super().__init__()
        surf = pygame.Surface((12, 5), pygame.SRCALPHA)
        surf.fill((255, 220, 80))
        self.image = surf
        self.rect = self.image.get_rect(center=(x, y))
        self.vel = 14 * direcao

    def update(self):
        self.rect.x += self.vel
        if self.rect.right < 0 or self.rect.left > LARGURA:
            self.kill()

class MegaManX(pygame.sprite.Sprite):
    def __init__(self, x=100, y=CHAO):
        super().__init__()
        # Tenta carregar em ordem prática: walk/run/jump/shoot/idle
        self.anim = {
            "idle": carregar_sprites_try(os.path.join(ASSETS_DIR, "idle")),
            "walk": carregar_sprites_try(os.path.join(ASSETS_DIR, "walk")),
            "run":  carregar_sprites_try(os.path.join(ASSETS_DIR, "run")),
            "jump": carregar_sprites_try(os.path.join(ASSETS_DIR, "jump")),
            "shoot":carregar_sprites_try(os.path.join(ASSETS_DIR, "shoot")),
        }
        # fallback se faltar animações: criamos um placeholder simples
        for k, v in list(self.anim.items()):
            if not v:
                s = pygame.Surface((48, 48), pygame.SRCALPHA)
                s.fill((0, 120, 255))
                self.anim[k] = [s]

        # estado inicial
        self.estado = "idle"
        self.frame = 0.0
        self.image = self.anim["idle"][0]
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.vel_y = 0.0
        self.direcao = 1
        self.tiros = pygame.sprite.Group()
        self.ultimo_tiro = 0
        self.anim_timer = 0
        self.som_tiro = SOUND_SHOOT
        self.som_pulo = SOUND_JUMP
        self.som_corrida = SOUND_RUN

    def update(self, teclas):
        self.anim_timer += 1
        velocidade_base = 4
        accel_run = 4  # deslocamento extra ao correr
        moved = False

        # Movimentação e estados
        correr = teclas[pygame.K_LSHIFT] or teclas[pygame.K_RSHIFT]
        if teclas[pygame.K_RIGHT]:
            self.direcao = 1
            self.rect.x += velocidade_base
            moved = True
            self.estado = "walk"
            if correr:
                self.rect.x += accel_run
                self.estado = "run"
                # som de passos (curto)
                if self.som_corrida and self.anim_timer % 12 == 0:
                    try:
                        self.som_corrida.play()
                    except: pass
        elif teclas[pygame.K_LEFT]:
            self.direcao = -1
            self.rect.x -= velocidade_base
            moved = True
            self.estado = "walk"
            if correr:
                self.rect.x -= accel_run
                self.estado = "run"
                if self.som_corrida and self.anim_timer % 12 == 0:
                    try:
                        self.som_corrida.play()
                    except: pass
        else:
            if self.estado not in ("jump", "shoot"):
                self.estado = "idle"

        # Dash (avanço rápido)
        if teclas[pygame.K_a]:
            self.rect.x += 10 * self.direcao
            self.estado = "run"

        # Pulo
        if teclas[pygame.K_SPACE] and self.rect.bottom >= CHAO:
            self.vel_y = -16
            self.estado = "jump"
            if self.som_pulo:
                try: self.som_pulo.play()
                except: pass

        # Atirar
        if teclas[pygame.K_z]:
            # controller: limita taxa de tiro
            agora = pygame.time.get_ticks()
            if agora - self.ultimo_tiro > 220:  # ms entre tiros
                self.ultimo_tiro = agora
                self.estado = "shoot"
                tx = self.rect.centerx + 30 * self.direcao
                ty = self.rect.centery - 6
                t = Tiro(tx, ty, self.direcao)
                self.tiros.add(t)
                if self.som_tiro:
                    try: self.som_tiro.play()
                    except: pass

        # Gravidade/queda
        self.vel_y += GRAVIDADE
        self.rect.y += self.vel_y
        if self.rect.bottom >= CHAO:
            self.rect.bottom = CHAO
            self.vel_y = 0.0

        # Limites de tela
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > LARGURA:
            self.rect.right = LARGURA

        # ANIMAÇÃO (controla frame index)
        frames = self.anim.get(self.estado) or self.anim["idle"]
        speed = 6 if self.estado == "run" else 9 if self.estado == "walk" else 12
        # quando pulo ou atiro com 1 frame, speed menor pra manter imagem
        if len(frames) == 1:
            speed = 999999

        if self.anim_timer % (FPS // (FPS // (speed if speed>0 else 1) )) == 0:
            self.frame = (self.frame + 1) % len(frames)

        # Seleciona frame e cria imagem de exibição
        frame_img = frames[int(self.frame)]
        display_img = frame_img.copy()

        # Determina necessidade de flip com base em SOURCE_FACING
        if SOURCE_FACING == "right":
            need_flip = (self.direcao == -1)
        else:
            need_flip = (self.direcao == 1)

        if need_flip:
            display_img = pygame.transform.flip(display_img, True, False)

        self.image = display_img
        # atualiza tiros
        self.tiros.update()

    def draw(self, surface):
        surface.blit(self.image, self.rect)
        self.tiros.draw(surface)

# --------------------
# Loop principal
# --------------------
def main():
    clock = pygame.time.Clock()
    player = MegaManX()
    rodando = True

    while rodando:
        dt = clock.tick(FPS)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                rodando = False

        teclas = pygame.key.get_pressed()
        player.update(teclas)

        # Desenho
        TELA.fill(BG)
        pygame.draw.rect(TELA, FLOOR_COLOR, (0, CHAO, LARGURA, 80))
        player.draw(TELA)

        # HUD simples (fps)
        fps_text = pygame.font.SysFont(None, 18).render(f"FPS: {int(clock.get_fps())}", True, WHITE)
        TELA.blit(fps_text, (8, 8))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
