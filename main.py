import pygame
import sys
import math
import random
import asyncio

# Initialize pygame
pygame.init()
WIDTH, HEIGHT = 800, 600
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Tower Defense")
CLOCK = pygame.time.Clock()

# Colors
GREEN = (34, 177, 76)
GRAY = (120, 120, 120)
RED = (200, 30, 30)
WHITE = (255, 255, 255)
BLUE = (50, 100, 200)
PURPLE = (150, 50, 200)
BROWN = (100, 60, 20)
YELLOW = (240, 230, 70)
ORANGE = (255, 150, 50)
ICE = (130, 210, 255)
FIRE = (255, 120, 0)
BLACK = (0, 0, 0)
UI_DARK = (25, 25, 30)
UI_LIGHT = (60, 60, 70)
UI_HIGHLIGHT = (80, 80, 100)

# Fonts
try:
    FONT = pygame.font.SysFont("Arial", 22)
    SMALL = pygame.font.SysFont("Arial", 18)
    BIG = pygame.font.SysFont("Arial", 48)
except:
    # Fallback fonts if system fonts aren't available
    FONT = pygame.font.Font(None, 22)
    SMALL = pygame.font.Font(None, 18)
    BIG = pygame.font.Font(None, 48)

# Game constants
STATE_MENU = "menu"
STATE_PLAY = "play"
STATE_GAMEOVER = "gameover"
STATE_INSTRUCTIONS = "instructions"
TOWER_MIN_SEP = 42

# Map/Path configuration
PATH = [
    (0, 250, 200, 100),
    (200, 250, 100, 300),
    (200, 450, 400, 100),
    (600, 150, 100, 400),
    (600, 150, 200, 100),
]
BASE_RECT = pygame.Rect(700, 150, 80, 80)

# Tower configuration
TOWER_TYPES = {
    "gun": {
        "name": "Gun",
        "color": YELLOW,
        "range": 120,
        "fire_rate": 22,
        "bullet_speed": 7,
        "damage": 22,
        "cost": 75,
        "description": "Basic tower with good damage and range"
    },
    "splash": {
        "name": "Splash",
        "color": FIRE,
        "range": 105,
        "fire_rate": 36,
        "bullet_speed": 6,
        "damage": 16,
        "splash_radius": 55,
        "cost": 100,
        "description": "Area damage, good against groups"
    },
    "freeze": {
        "name": "Freeze",
        "color": ICE,
        "range": 115,
        "fire_rate": 30,
        "bullet_speed": 6,
        "damage": 10,
        "slow_factor": 0.5,
        "slow_time": 120,
        "cost": 90,
        "description": "Slows enemies, good for support"
    },
}

# Generate waypoints from path segments
WAYPOINTS = []
for seg in PATH:
    x, y, w, h = seg
    if w > h:  # Horizontal segment
        steps = w // 20
        for i in range(steps + 1):
            WAYPOINTS.append((x + i * w / steps, y + h/2))
    else:  # Vertical segment
        steps = h // 20
        for i in range(steps + 1):
            WAYPOINTS.append((x + w/2, y + i * h / steps))


class Enemy:
    def __init__(self, kind="normal"):
        self.kind = kind
        self.x, self.y = WAYPOINTS[0]
        self.waypoint_index = 0
        self.radius = 15
        self.slow_timer = 0
        self.slow_factor_active = 1.0
        
        if kind == "normal":
            self.color = BLUE
            self.max_health = 100
            self.health = 100
            self.speed_base = 2.0
            self.reward = 20
        elif kind == "fast":
            self.color = PURPLE
            self.max_health = 60
            self.health = 60
            self.speed_base = 3.4
            self.reward = 15
        else:  # tank
            self.color = BROWN
            self.max_health = 250
            self.health = 250
            self.speed_base = 1.2
            self.reward = 40

    @property
    def speed(self):
        if self.slow_timer > 0:
            return self.speed_base * self.slow_factor_active
        return self.speed_base

    def apply_slow(self, factor, duration_frames):
        if self.slow_timer <= 0 or factor < self.slow_factor_active or duration_frames > self.slow_timer:
            self.slow_factor_active = max(0.25, factor)
            self.slow_timer = duration_frames

    def move(self):
        if self.waypoint_index < len(WAYPOINTS) - 1:
            tx, ty = WAYPOINTS[self.waypoint_index + 1]
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            spd = self.speed
            
            if dist < spd:
                self.waypoint_index += 1
                if self.waypoint_index < len(WAYPOINTS) - 1:
                    tx, ty = WAYPOINTS[self.waypoint_index + 1]
                    dx, dy = tx - self.x, ty - self.y
                    dist = math.hypot(dx, dy)
            
            if dist > 0:
                self.x += spd * dx / dist
                self.y += spd * dy / dist
        
        if self.slow_timer > 0:
            self.slow_timer -= 1

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)
        
        # HP bar
        w = 32
        ratio = max(self.health / self.max_health, 0)
        pygame.draw.rect(surf, RED, (self.x - w/2, self.y - 25, w, 5))
        pygame.draw.rect(surf, (0, 220, 0), (self.x - w/2, self.y - 25, w*ratio, 5))
        
        # Slow outline
        if self.slow_timer > 0:
            pygame.draw.circle(surf, ICE, (int(self.x), int(self.y)), self.radius+2, 1)


class Bullet:
    def __init__(self, x, y, target, tower_type):
        self.x, self.y = x, y
        self.target = target
        self.tower_type = tower_type
        cfg = TOWER_TYPES[tower_type]
        self.speed = cfg["bullet_speed"]
        self.damage = cfg["damage"]
        self.radius = 5
        self.dead = False

    def update(self, enemies, particles):
        if self.target is None or self.dead:
            return
        
        if self.target.health <= 0:
            self.dead = True
            return
            
        dx, dy = self.target.x - self.x, self.target.y - self.y
        dist = math.hypot(dx, dy)
        
        if dist < max(6, self.speed) or self.target.health <= 0:
            self.impact(enemies, particles)
            self.dead = True
            return
            
        self.x += self.speed * dx / (dist + 1e-6)
        self.y += self.speed * dy / (dist + 1e-6)

    def impact(self, enemies, particles):
        for _ in range(6):
            particles.append(Particle(self.x, self.y))
            
        if self.tower_type == "splash":
            r = TOWER_TYPES["splash"]["splash_radius"]
            for e in enemies:
                if math.hypot(e.x - self.x, e.y - self.y) <= r:
                    e.health -= self.damage
        elif self.tower_type == "freeze":
            e = self.target
            e.health -= self.damage
            e.apply_slow(TOWER_TYPES["freeze"]["slow_factor"], TOWER_TYPES["freeze"]["slow_time"])
        else:
            self.target.health -= self.damage

    def draw(self, surf):
        color = (ORANGE if self.tower_type == "gun" else 
                 FIRE if self.tower_type == "splash" else 
                 ICE)
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), self.radius)


class Tower:
    def __init__(self, x, y, tower_type="gun"):
        self.x, self.y = x, y
        self.type = tower_type
        cfg = TOWER_TYPES[tower_type]
        self.range = cfg["range"]
        self.fire_rate = cfg["fire_rate"]
        self.cooldown = 0
        self.level = 1
        self.color = cfg["color"]

    def in_range(self, enemy):
        return math.hypot(enemy.x - self.x, enemy.y - self.y) <= self.range

    def try_shoot(self, enemies, bullets):
        if self.cooldown > 0:
            self.cooldown -= 1
            return
            
        target = None
        best_idx = -1
        for e in enemies:
            if self.in_range(e):
                if e.waypoint_index > best_idx:
                    best_idx = e.waypoint_index
                    target = e
                    
        if target:
            bullets.append(Bullet(self.x, self.y, target, self.type))
            self.cooldown = max(6, self.fire_rate)

    def upgrade_cost(self):
        base = int(TOWER_TYPES[self.type]["cost"] * 0.6)
        return base * self.level

    def upgrade(self):
        if self.level >= 3:
            return False
        self.level += 1
        self.range = int(self.range * 1.15)
        self.fire_rate = max(6, int(self.fire_rate * 0.85))
        return True

    def draw(self, surf, selected=False):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), 20)
        if selected:
            pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), 22, 2)
            
        for i in range(self.level):
            pygame.draw.circle(surf, UI_LIGHT, (int(self.x) - 14 + i*14, int(self.y) - 22), 3)


class Particle:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = random.uniform(-1.5, 1.5)
        self.vy = random.uniform(-2.0, -0.2)
        self.life = random.randint(12, 22)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.12
        self.life -= 1

    def draw(self, surf):
        if self.life > 0:
            pygame.draw.circle(surf, (255, 220, 120), (int(self.x), int(self.y)), 2)


class Button:
    def __init__(self, x, y, width, height, text, color=UI_LIGHT, hover_color=UI_HIGHLIGHT, text_color=WHITE):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False
        
    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=5)
        
        text_surf = SMALL.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
        
    def check_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered
        
    def is_clicked(self, pos, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(pos)
        return False


class Game:
    def __init__(self):
        self.state = STATE_MENU
        self.enemies = []
        self.towers = []
        self.bullets = []
        self.particles = []
        self.base_health = 12
        self.money = 180
        self.score = 0
        self.wave = 0
        self.wave_active = False
        self.wave_queue = []
        self.spawn_timer = 0
        self.selected_type = "gun"
        self.selected_tower = None
        self.instructions_scroll = 0
        self.scroll_speed = 20
        
    def draw_background(self):
        WIN.fill(GREEN)
        for seg in PATH:
            pygame.draw.rect(WIN, GRAY, seg)
        pygame.draw.rect(WIN, RED, BASE_RECT)
        
    def is_on_path_or_base(self, x, y):
        p = pygame.Rect(0, 0, 40, 40)
        p.center = (x, y)
        if p.colliderect(BASE_RECT):
            return True
        for seg in PATH:
            if p.colliderect(pygame.Rect(seg)):
                return True
        return False
        
    def is_overlapping_tower(self, x, y, towers):
        for t in towers:
            if math.hypot(t.x - x, t.y - y) < TOWER_MIN_SEP:
                return True
        return False
        
    def draw_hud(self):
        pygame.draw.rect(WIN, UI_DARK, (0, 0, WIDTH, 36))
        txt = FONT.render(f"Money: ${self.money} | Base: {self.base_health} | Wave: {self.wave} | Score: {self.score}", True, WHITE)
        WIN.blit(txt, (10, 6))
        
        names = [("1", "Gun", TOWER_TYPES["gun"]["cost"], YELLOW),
                 ("2", "Splash", TOWER_TYPES["splash"]["cost"], FIRE),
                 ("3", "Freeze", TOWER_TYPES["freeze"]["cost"], ICE)]
        x = 420
        for key, name, cost, col in names:
            box = pygame.Rect(x, 4, 115, 28)
            color = UI_HIGHLIGHT if self.selected_type == name.lower() else UI_LIGHT
            pygame.draw.rect(WIN, color, box, border_radius=3)
            pygame.draw.rect(WIN, col, box, 2, border_radius=3)
            label = SMALL.render(f"{key}:{name} ${cost}", True, WHITE)
            WIN.blit(label, (x+6, 8))
            x += 125
            
        if not self.wave_active:
            tip = SMALL.render("Press SPACE to start next wave", True, WHITE)
            WIN.blit(tip, (WIDTH - tip.get_width() - 12, 8))
            
    def draw_range_preview(self, mx, my):
        if self.selected_type is None:
            return
        rng = TOWER_TYPES[self.selected_type]["range"]
        color = (0, 255, 0, 100) if self.is_valid_placement(mx, my) else (255, 0, 0, 100)
        
        surf = pygame.Surface((rng*2, rng*2), pygame.SRCALPHA)
        pygame.draw.circle(surf, color, (rng, rng), rng)
        WIN.blit(surf, (mx - rng, my - rng))
        
        pygame.draw.circle(WIN, TOWER_TYPES[self.selected_type]["color"], (mx, my), 20, 2)
        
    def is_valid_placement(self, x, y):
        return (self.money >= TOWER_TYPES[self.selected_type]["cost"] and 
                not self.is_on_path_or_base(x, y) and 
                not self.is_overlapping_tower(x, y, self.towers))
        
    def generate_wave(self):
        wave = []
        count = 5 + self.wave * 2
        if self.wave < 3:
            pool = ["normal"] * 8 + ["fast"] * 2
        elif self.wave < 6:
            pool = ["normal"] * 6 + ["fast"] * 3 + ["tank"] * 1
        else:
            pool = ["normal"] * 4 + ["fast"] * 3 + ["tank"] * 3
            
        for _ in range(count):
            wave.append(random.choice(pool))
        return wave
        
    def draw_instructions(self):
        WIN.fill(UI_DARK)
        
        title = BIG.render("INSTRUCTIONS", True, WHITE)
        WIN.blit(title, (WIDTH//2 - title.get_width()//2, 20 - self.instructions_scroll))
        
        sections = [
            {
                "title": "GAME OBJECTIVE",
                "content": [
                    "Protect your base from enemy attacks by building towers along the path.",
                    "Earn money by defeating enemies and use it to build and upgrade towers.",
                    "Survive as many waves as possible to achieve a high score!"
                ]
            },
            {
                "title": "CONTROLS",
                "content": [
                    "1-3: Select tower type (Gun, Splash, Freeze)",
                    "Mouse: Place selected tower (green circle = valid placement)",
                    "U: Upgrade selected tower",
                    "SPACE: Start next wave",
                    "ESC: Deselect tower / Return to menu",
                    "I: Toggle instructions during gameplay"
                ]
            }
        ]
        
        y_pos = 80 - self.instructions_scroll
        for section in sections:
            title_text = FONT.render(section["title"], True, YELLOW)
            WIN.blit(title_text, (WIDTH//2 - title_text.get_width()//2, y_pos))
            y_pos += 40
            
            for line in section["content"]:
                text = SMALL.render(line, True, WHITE)
                WIN.blit(text, (40, y_pos))
                y_pos += 25
            y_pos += 10
        
        back_btn = Button(WIDTH//2 - 60, HEIGHT - 50, 120, 40, "Back to Menu")
        mouse_pos = pygame.mouse.get_pos()
        back_btn.check_hover(mouse_pos)
        back_btn.draw(WIN)
        
        return back_btn
        
    def draw_game_over(self):
        WIN.fill(UI_DARK)
        
        over = BIG.render("GAME OVER", True, RED)
        WIN.blit(over, (WIDTH//2 - over.get_width()//2, 150))
        
        stats = FONT.render(f"Final Score: {self.score} | Waves Survived: {self.wave}", True, WHITE)
        WIN.blit(stats, (WIDTH//2 - stats.get_width()//2, 220))
        
        restart_btn = Button(WIDTH//2 - 140, 300, 120, 50, "Restart", UI_LIGHT, UI_HIGHLIGHT)
        menu_btn = Button(WIDTH//2 + 20, 300, 120, 50, "Main Menu", UI_LIGHT, UI_HIGHLIGHT)
        
        mouse_pos = pygame.mouse.get_pos()
        restart_btn.check_hover(mouse_pos)
        menu_btn.check_hover(mouse_pos)
        
        restart_btn.draw(WIN)
        menu_btn.draw(WIN)
        
        return restart_btn, menu_btn
        
    def draw_main_menu(self):
        WIN.fill(UI_DARK)
        
        title = BIG.render("TOWER DEFENSE", True, WHITE)
        WIN.blit(title, (WIDTH//2 - title.get_width()//2, 120))
        
        subtitle = FONT.render("Enhanced Edition", True, YELLOW)
        WIN.blit(subtitle, (WIDTH//2 - subtitle.get_width()//2, 180))
        
        play_btn = Button(WIDTH//2 - 100, 250, 200, 50, "Play Game", UI_LIGHT, UI_HIGHLIGHT)
        instructions_btn = Button(WIDTH//2 - 100, 320, 200, 50, "Instructions", UI_LIGHT, UI_HIGHLIGHT)
        quit_btn = Button(WIDTH//2 - 100, 390, 200, 50, "Quit Game", UI_LIGHT, UI_HIGHLIGHT)
        
        mouse_pos = pygame.mouse.get_pos()
        play_btn.check_hover(mouse_pos)
        instructions_btn.check_hover(mouse_pos)
        quit_btn.check_hover(mouse_pos)
        
        play_btn.draw(WIN)
        instructions_btn.draw(WIN)
        quit_btn.draw(WIN)
        
        hint = SMALL.render("Press I during gameplay to view instructions", True, WHITE)
        WIN.blit(hint, (WIDTH//2 - hint.get_width()//2, 480))
        
        return play_btn, instructions_btn, quit_btn
        
    def update_game(self):
        if self.wave_active:
            self.spawn_timer += 1
            if self.spawn_timer >= 58 and self.wave_queue:
                kind = self.wave_queue.pop(0)
                self.enemies.append(Enemy(kind))
                self.spawn_timer = 0
            if not self.wave_queue and not self.enemies:
                self.wave_active = False
                self.money += 30 + self.wave * 5
                self.score += self.wave * 10
                
        for e in self.enemies[:]:
            e.move()
            if e.waypoint_index >= len(WAYPOINTS) - 1:
                self.enemies.remove(e)
                self.base_health -= 1
                if self.base_health <= 0:
                    self.state = STATE_GAMEOVER
                    
        for t in self.towers:
            t.try_shoot(self.enemies, self.bullets)
            
        for b in self.bullets[:]:
            b.update(self.enemies, self.particles)
            if b.dead:
                self.bullets.remove(b)
                
        for e in self.enemies[:]:
            if e.health <= 0:
                self.score += e.reward
                self.money += e.reward // 2
                self.enemies.remove(e)
                
        for p in self.particles[:]:
            p.update()
            if p.life <= 0:
                self.particles.remove(p)
                
    def draw_game(self):
        self.draw_background()
        
        for e in self.enemies:
            e.draw(WIN)
        for t in self.towers:
            t.draw(WIN, self.selected_tower is t)
        for b in self.bullets:
            b.draw(WIN)
        for p in self.particles:
            p.draw(WIN)
            
        self.draw_hud()
        
        mx, my = pygame.mouse.get_pos()
        if 36 < my < HEIGHT:
            self.draw_range_preview(mx, my)
            
        if self.selected_tower:
            panel = pygame.Rect(10, HEIGHT - 86, 330, 76)
            pygame.draw.rect(WIN, UI_DARK, panel, border_radius=5)
            pygame.draw.rect(WIN, UI_LIGHT, panel, 2, border_radius=5)
            name = TOWER_TYPES[self.selected_tower.type]["name"]
            info1 = SMALL.render(
                f"{name} Tower Lvl {self.selected_tower.level} Range:{self.selected_tower.range} Rate:{self.selected_tower.fire_rate}", 
                True, WHITE)
            WIN.blit(info1, (panel.x + 10, panel.y + 10))
            
            up_cost = self.selected_tower.upgrade_cost() if self.selected_tower.level < 3 else None
            if up_cost:
                info2 = SMALL.render(f"Press U to Upgrade (${up_cost})", True, WHITE)
            else:
                info2 = SMALL.render("Max Level Reached", True, WHITE)
            WIN.blit(info2, (panel.x + 10, panel.y + 36))
            
    def reset(self):
        self.__init__()


async def main():
    game_instance = Game()
    running = True
    
    while running:
        CLOCK.tick(60)
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            if game_instance.state == STATE_MENU:
                play_btn, instructions_btn, quit_btn = game_instance.draw_main_menu()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if play_btn.is_clicked(mouse_pos, event):
                        game_instance.state = STATE_PLAY
                    elif instructions_btn.is_clicked(mouse_pos, event):
                        game_instance.state = STATE_INSTRUCTIONS
                        game_instance.instructions_scroll = 0
                    elif quit_btn.is_clicked(mouse_pos, event):
                        running = False
                        
            elif game_instance.state == STATE_INSTRUCTIONS:
                back_btn = game_instance.draw_instructions()
                
                if event.type == pygame.MOUSEWHEEL:
                    game_instance.instructions_scroll -= event.y * game_instance.scroll_speed
                    game_instance.instructions_scroll = max(0, min(game_instance.instructions_scroll, 1000))
                
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if back_btn.is_clicked(mouse_pos, event):
                        game_instance.state = STATE_MENU
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    game_instance.state = STATE_MENU
                    
            elif game_instance.state == STATE_GAMEOVER:
                restart_btn, menu_btn = game_instance.draw_game_over()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if restart_btn.is_clicked(mouse_pos, event):
                        game_instance.reset()
                    elif menu_btn.is_clicked(mouse_pos, event):
                        game_instance.state = STATE_MENU
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        game_instance.reset()
                    elif event.key == pygame.K_ESCAPE:
                        game_instance.state = STATE_MENU
                        
            elif game_instance.state == STATE_PLAY:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE and not game_instance.wave_active:
                        game_instance.wave += 1
                        game_instance.wave_queue = game_instance.generate_wave()
                        game_instance.wave_active = True
                    if event.key == pygame.K_1:
                        game_instance.selected_type = "gun"
                    if event.key == pygame.K_2:
                        game_instance.selected_type = "splash"
                    if event.key == pygame.K_3:
                        game_instance.selected_type = "freeze"
                    if event.key == pygame.K_ESCAPE:
                        game_instance.selected_tower = None
                    if event.key == pygame.K_u and game_instance.selected_tower:
                        cost = game_instance.selected_tower.upgrade_cost()
                        if game_instance.selected_tower.level < 3 and game_instance.money >= cost:
                            if game_instance.selected_tower.upgrade():
                                game_instance.money -= cost
                    if event.key == pygame.K_i:
                        game_instance.state = STATE_INSTRUCTIONS
                        game_instance.instructions_scroll = 0
                
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    clicked_existing = False
                    for t in game_instance.towers:
                        if math.hypot(t.x - mx, t.y - my) <= 22:
                            game_instance.selected_tower = t
                            clicked_existing = True
                            break
                    
                    if clicked_existing:
                        continue
                    
                    cost = TOWER_TYPES[game_instance.selected_type]["cost"]
                    valid = game_instance.is_valid_placement(mx, my)
                    if valid:
                        game_instance.towers.append(Tower(mx, my, game_instance.selected_type))
                        game_instance.money -= cost
                        game_instance.selected_tower = None

        if game_instance.state == STATE_MENU:
            game_instance.draw_main_menu()
        elif game_instance.state == STATE_INSTRUCTIONS:
            game_instance.draw_instructions()
        elif game_instance.state == STATE_GAMEOVER:
            game_instance.draw_game_over()
        elif game_instance.state == STATE_PLAY:
            game_instance.update_game()
            game_instance.draw_game()
            
        pygame.display.update()
        await asyncio.sleep(0)
        
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())