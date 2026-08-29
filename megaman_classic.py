import pygame
import sys
import os
import numpy as np
import wave
import struct

# --- INICIALIZAÇÕES IMPORTANTES ---
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.mixer.init()

# --- CONFIGURAÇÕES ---
LARGURA, ALTURA = 800, 400
TELA = pygame.display.set_mode((LARGURA, ALTURA))
pygame.display.set_caption("Mega Man Clássico - Corrigido")
FPS = 60

# --- CORES E CHÃO ---
AZUL = (50, 100, 255)
CHAO = ALTURA - 80

# --- GERAR SONS ---
def gerar_som(nome, frequencia, duracao, tipo="quadrada"):
    os.makedirs("assets/sounds", exist_ok=True)
    taxa = 44100
    t = np.linspace(0, duracao, int(taxa * duracao), False)
    if tipo == "quadrada":
        onda = 0.5 * np.sign(np.sin(2 * np.pi * frequencia * t))
    elif tipo == "senoide":
        onda = 0.5 * np.sin(2 * np.pi * frequencia * t)
    onda = np.int16(onda * 32767)
    caminho = f"assets/sounds/{nome}.wav"
    with wave.open(caminho, "w") as f:
        f.setparams((1, 2, taxa, 0, "NONE", "not compressed"))
        for s in onda:
            f.writeframes(struct.pack("h", s))
    return caminho

# Sons simples
som_tiro = gerar_som("shoot", 880, 0.1)
som_pulo = gerar_som("jump", 440, 0.25)

# --- FUNÇÃO PARA CARREGAR SPRITES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_sprites(caminho):
    sprites = []
    if not os.path.exists(caminho):
        print(f"[AVISO] Pasta não encontrada: {caminho}")
        return sprites
    for arquivo in sorted(os.listdir(caminho)):
        if arquivo.lower().endswith(".png"):
            imagem = pygame.image.load(os.path.join(caminho, arquivo)).convert_alpha()
            sprites.append(imagem)
    print(f"✅ {caminho}: {len(sprites)} sprite(s) carregado(s).")
    return sprites

# --- CLASSE TIRO ---
class Tiro(pygame.sprite.Sprite):
    def __init__(self, x, y, direcao):
        super().__init__()
        self.image = pygame.Surface((10, 4))
        self.image.fill((255, 255, 0))
        self.rect = self.image.get_rect(center=(x, y))
        self.velocidade = 10 * direcao

    def update(self):
        self.rect.x += self.velocidade
        if self.rect.right < 0 or self.rect.left > LARGURA:
            self.kill()

# -------------------------
# Classe MegaMan (substituir a sua)
# -------------------------
class MegaMan(pygame.sprite.Sprite):
    # Configure aqui dependendo dos seus sprites:
    # SOURCE_FACING: "right" se os frames já olham para a direita,
    #                 "left"  se os frames olham para a esquerda.
    # REVERSE_WALK_FRAMES: True  -> inverte a ordem dos frames de walk (se as pernas parecerem trocadas)
    SOURCE_FACING = "left"        # experimente "left" ou "right"
    REVERSE_WALK_FRAMES = False   # experimente True se a caminhada ficar estranha

    def __init__(self):
        super().__init__()

        self.animacoes = {
            "walk": carregar_sprites(os.path.join(BASE_DIR, "assets", "megaman1", "walk")),
            "jump": carregar_sprites(os.path.join(BASE_DIR, "assets", "megaman1", "jump")),
            "shoot": carregar_sprites(os.path.join(BASE_DIR, "assets", "megaman1", "shoot")),
        }

        # se walk estiver vazia, cria placeholder
        if not self.animacoes["walk"]:
            self.animacoes["walk"] = [pygame.Surface((40,40))]
            self.animacoes["walk"][0].fill(AZUL)

        # aplica reverse se necessário (corrige ordem de frames)
        if MegaMan.REVERSE_WALK_FRAMES and len(self.animacoes["walk"]) > 1:
            self.animacoes["walk"].reverse()

        # usa walk como idle se não houver idle
        self.animacoes["idle"] = self.animacoes["walk"]

        self.estado = "idle"
        self.frame = 0.0
        self.image = self.animacoes["idle"][0]
        self.rect = self.image.get_rect(midbottom=(100, CHAO))
        self.vel_y = 0
        self.no_chao = True
        self.direcao = 1    # 1 = direita, -1 = esquerda
        self.anim_timer = 0
        # sons (supondo gerados anteriormente)
        try:
            self.som_tiro = pygame.mixer.Sound(som_tiro)
            self.som_pulo = pygame.mixer.Sound(som_pulo)
        except Exception:
            self.som_tiro = None
            self.som_pulo = None

    def atualizar(self, teclas, tiros):
        velocidade = 5
        gravidade = 1
        self.anim_timer += 1

        # Movimento horizontal
        if teclas[pygame.K_LEFT]:
            self.rect.x -= velocidade
            self.direcao = -1
            self.estado = "walk"
        elif teclas[pygame.K_RIGHT]:
            self.rect.x += velocidade
            self.direcao = 1
            self.estado = "walk"
        else:
            self.estado = "idle"

        # Pular
        if teclas[pygame.K_SPACE] and self.no_chao:
            self.vel_y = -15
            self.no_chao = False
            self.estado = "jump"
            if self.som_pulo:
                self.som_pulo.play()

        # Gravidade
        self.vel_y += gravidade
        self.rect.y += self.vel_y
        if self.rect.bottom >= CHAO:
            self.rect.bottom = CHAO
            self.vel_y = 0
            self.no_chao = True

        # Atirar (limite de rate)
        if teclas[pygame.K_z]:
            self.estado = "shoot"
            if not hasattr(self, "ultimo_tiro") or pygame.time.get_ticks() - self.ultimo_tiro > 300:
                tiro = Tiro(self.rect.centerx + 25 * self.direcao, self.rect.centery, self.direcao)
                tiros.add(tiro)
                if self.som_tiro:
                    self.som_tiro.play()
                self.ultimo_tiro = pygame.time.get_ticks()

        # Animação: atualiza frame index
        frames = self.animacoes.get(self.estado) or self.animacoes["walk"]
        if frames:
            # velocidade de troca dos frames (ajuste 0.2-0.4 para mais/menos rapidez)
            self.frame += 0.28
            if self.frame >= len(frames):
                self.frame = 0.0
            frame_img = frames[int(self.frame)]
        else:
            frame_img = pygame.Surface((40, 40))
            frame_img.fill(AZUL)

        # NÃO sobrescreve o frame original (importante)
        display_img = frame_img.copy()

        # Decidir se precisa flipar horizontalmente:
        # - se as imagens de origem olham para "right": flip quando direcao == -1
        # - se as imagens de origem olham para "left":  flip quando direcao ==  1
        if MegaMan.SOURCE_FACING == "right":
            need_flip = (self.direcao == -1)
        else:  # SOURCE_FACING == "left"
            need_flip = (self.direcao == 1)

        if need_flip:
            display_img = pygame.transform.flip(display_img, True, False)

        self.image = display_img


        # Espelhar se estiver indo para a esquerda
        if self.direcao == -1:
            self.image = pygame.transform.flip(self.image, True, False)

# --- LOOP PRINCIPAL ---
def main():
    clock = pygame.time.Clock()
    jogador = MegaMan()
    tiros = pygame.sprite.Group()

    rodando = True
    while rodando:
        clock.tick(FPS)
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                rodando = False
                pygame.quit()
                sys.exit()

        teclas = pygame.key.get_pressed()
        jogador.atualizar(teclas, tiros)
        tiros.update()

        # --- DESENHAR ---
        TELA.fill((40, 120, 255))
        pygame.draw.rect(TELA, (100, 60, 20), (0, CHAO, LARGURA, 80))
        TELA.blit(jogador.image, jogador.rect)
        tiros.draw(TELA)
        pygame.display.flip()

if __name__ == "__main__":
    main()
