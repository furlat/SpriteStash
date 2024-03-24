from pydantic import BaseModel, Field
from typing import List, Optional
import os
import json
import pygame
import os

class Sprite(BaseModel):
    name: str = ""
    image_url: str
    description: str = ""
    image: Optional[pygame.Surface] = None
    class Config:
        arbitrary_types_allowed = True
    def load_image(self):
        if self.image_url:
            self.image = pygame.image.load(self.image_url).convert_alpha()

class StateSequence(BaseModel):
    name: str
    sprites: List[Sprite]
    description: str = ""

class SpriteEntity(BaseModel):
    name: str
    states: List[StateSequence]
    source: str = ""
    description: str = ""
    sprite_width: int = 0
    sprite_height: int = 0

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def load_from_file(cls, file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
        sprite_entity = cls(**data)
        for state in sprite_entity.states:
            for sprite in state.sprites:
                sprite.load_image()
        return sprite_entity

    @classmethod
    def load_from_spritesheet(cls, spritesheet_path, sprite_width, sprite_height):
        spritesheet = pygame.image.load(spritesheet_path).convert_alpha()
        states = []
        for y in range(0, spritesheet.get_height(), sprite_height):
            sprites = []
            for x in range(0, spritesheet.get_width(), sprite_width):
                sprite_image = spritesheet.subsurface((x, y, sprite_width, sprite_height))
                if not cls.is_sprite_empty(sprite_image):
                    sprite = Sprite(image=sprite_image, image_url="")
                    sprites.append(sprite)
            if sprites:
                states.append(StateSequence(name=f"State{len(states)}", sprites=sprites))
        sprite_entity = cls(
            name=os.path.splitext(os.path.basename(spritesheet_path))[0],
            states=states,
            source=spritesheet_path,
            sprite_width=sprite_width,
            sprite_height=sprite_height
        )
        return sprite_entity

    @staticmethod
    def is_sprite_empty(sprite_image):
        return not bool(sprite_image.get_bounding_rect())

    def save_to_file(self, folder_path):
        os.makedirs(folder_path, exist_ok=True)
        for state_index, state in enumerate(self.states):
            for sprite_index, sprite in enumerate(state.sprites):
                image_url = os.path.join(folder_path, f"state_{state_index}_sprite_{sprite_index}.png")
                pygame.image.save(sprite.image, image_url)
                sprite.image_url = image_url
                sprite.image = None
        data = self.dict(exclude={'states': {'sprites': {'image'}}})
        with open(os.path.join(folder_path, "metadata.json"), 'w') as file:
            json.dump(data, file, indent=4)
        # Reload the images after saving
        for state in self.states:
            for sprite in state.sprites:
                sprite.load_image()

class SpriteManager:
    def __init__(self, spritesheet_path, sprite_width, sprite_height, scale_factor=1.0):
        self.spritesheet_folder = os.path.dirname(spritesheet_path)
        self.spritesheet_files = self.get_spritesheet_files(self.spritesheet_folder)
        self.current_spritesheet_index = self.spritesheet_files.index(os.path.basename(spritesheet_path))
        self.spritesheet_path = os.path.join(self.spritesheet_folder, self.spritesheet_files[self.current_spritesheet_index])
        self.initial_sprite_width = sprite_width
        self.initial_sprite_height = sprite_height
        self.sprite_width = sprite_width
        self.sprite_height = sprite_height
        self.scale_factor = scale_factor
        self.sprite_entity = None
        self.current_state_index = 0
        self.current_sprite_index = 0
        self.is_playing = False
        self.speed = 1
        self.frame_delay = 0
        self.frame_timer = 0
        self.load_spritesheet()

    
    def get_spritesheet_files(self, folder_path):
        return [file for file in os.listdir(folder_path) if file.endswith(".png")]
    
    def load_spritesheet(self):
        try:
            spritesheet = pygame.image.load(self.spritesheet_path).convert_alpha()
            spritesheet_width, spritesheet_height = spritesheet.get_size()

            # Adjust sprite width and height based on spritesheet dimensions
            self.sprite_width = min(self.sprite_width, spritesheet_width)
            self.sprite_height = min(self.sprite_height, spritesheet_height)

            states = []
            for y in range(0, spritesheet_height, self.sprite_height):
                sprites = []
                for x in range(0, spritesheet_width, self.sprite_width):
                    sprite_rect = pygame.Rect(x, y, self.sprite_width, self.sprite_height)
                    if sprite_rect.right <= spritesheet_width and sprite_rect.bottom <= spritesheet_height:
                        sprite_image = spritesheet.subsurface(sprite_rect)
                        if not self.is_sprite_empty(sprite_image):
                            sprite = Sprite(image=sprite_image, image_url="")
                            sprites.append(sprite)
                if sprites:
                    states.append(StateSequence(name=f"State{len(states)}", sprites=sprites))

            self.sprite_entity = SpriteEntity(
                name=os.path.splitext(os.path.basename(self.spritesheet_path))[0],
                states=states,
                source=self.spritesheet_path,
                sprite_width=self.sprite_width,
                sprite_height=self.sprite_height
            )
        except (ValueError, pygame.error) as e:
            print(f"Error loading spritesheet: {str(e)}")
            self.sprite_entity = None

    def next_spritesheet(self):
        self.current_spritesheet_index = (self.current_spritesheet_index + 1) % len(self.spritesheet_files)
        self.spritesheet_path = os.path.join(self.spritesheet_folder, self.spritesheet_files[self.current_spritesheet_index])
        self.sprite_width = self.initial_sprite_width
        self.sprite_height = self.initial_sprite_height
        self.current_state_index = 0
        self.current_sprite_index = 0
        self.load_spritesheet()

    def previous_spritesheet(self):
        self.current_spritesheet_index = (self.current_spritesheet_index - 1) % len(self.spritesheet_files)
        self.spritesheet_path = os.path.join(self.spritesheet_folder, self.spritesheet_files[self.current_spritesheet_index])
        self.sprite_width = self.initial_sprite_width
        self.sprite_height = self.initial_sprite_height
        self.current_state_index = 0
        self.current_sprite_index = 0
        self.load_spritesheet()

    def render_input_boxes(self, screen, text_boxes, active_text_box):
        font = pygame.font.Font(None, 24)
        for i, text_box in enumerate(text_boxes):
            if i == active_text_box:
                pygame.draw.rect(screen, (200, 200, 200), text_box)

            else:
                pygame.draw.rect(screen, (255, 255, 255), text_box)
            pygame.draw.rect(screen, (0, 0, 0), text_box, 2)
            if i == 0:
                text = str(self.sprite_width)
            elif i == 1:
                text = str(self.sprite_height)
            elif i == 2:
                text = self.sprite_entity.name if self.sprite_entity else ""
            elif i == 3:
                text = self.sprite_entity.description if self.sprite_entity else ""
            elif i == 4:
                text = self.sprite_entity.states[self.current_state_index].name if self.sprite_entity else ""
            elif i == 5:
                text = self.sprite_entity.states[self.current_state_index].description if self.sprite_entity else ""
            # elif i ==7:
            #     text = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].name if self.sprite_entity else ""
            # elif i == 8:
            #     text = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].description if self.sprite_entity else ""
            else:
                text = ""
            text_surface = font.render(text, True, (0, 0, 0))
            screen.blit(text_surface, (text_box.x + 5, text_box.y + 5))

    def handle_key_events(self, event, active_text_box):
        if active_text_box is None:
            if self.sprite_entity is not None:
                if event.key == pygame.K_LEFT:
                    self.current_sprite_index = (self.current_sprite_index - 1) % len(self.sprite_entity.states[self.current_state_index].sprites)
                elif event.key == pygame.K_RIGHT:
                    self.current_sprite_index = (self.current_sprite_index + 1) % len(self.sprite_entity.states[self.current_state_index].sprites)
                elif event.key == pygame.K_UP:
                    self.current_state_index = (self.current_state_index - 1) % len(self.sprite_entity.states)
                    self.current_sprite_index = 0
                elif event.key == pygame.K_DOWN:
                    self.current_state_index = (self.current_state_index + 1) % len(self.sprite_entity.states)
                    self.current_sprite_index = 0
                elif event.key == pygame.K_SPACE:
                    self.is_playing = not self.is_playing
                elif event.key == pygame.K_s:
                    self.save_sprite_entity()
                elif event.key == pygame.K_l:
                    self.load_sprite_entity()
                elif event.key == pygame.K_COMMA:
                    self.previous_spritesheet()
                elif event.key == pygame.K_PERIOD:
                    self.next_spritesheet()
        else:
            if event.key == pygame.K_RETURN:
                active_text_box = None
            elif event.key == pygame.K_BACKSPACE:
                if active_text_box == 0:
                    self.sprite_width = int(str(self.sprite_width)[:-1]) if str(self.sprite_width)[:-1] else 0
                elif active_text_box == 1:
                    self.sprite_height = int(str(self.sprite_height)[:-1]) if str(self.sprite_height)[:-1] else 0
                elif active_text_box == 2:
                    self.sprite_entity.name = self.sprite_entity.name[:-1]
                elif active_text_box == 3:
                    self.sprite_entity.description = self.sprite_entity.description[:-1]
                elif active_text_box == 4:
                    self.sprite_entity.states[self.current_state_index].name = self.sprite_entity.states[self.current_state_index].name[:-1]
                elif active_text_box == 5:
                    self.sprite_entity.states[self.current_state_index].description = self.sprite_entity.states[self.current_state_index].description[:-1]
                elif active_text_box == 6:
                    self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].name = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].name[:-1]
                elif active_text_box == 7:
                    self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].description = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].description[:-1]
            else:
                if active_text_box == 0:
                    if event.unicode.isdigit():
                        self.sprite_width = int(str(self.sprite_width) + event.unicode)
                        self.load_spritesheet()
                        self.current_state_index = 0
                        self.current_sprite_index = 0
                elif active_text_box == 1:
                    if event.unicode.isdigit():
                        self.sprite_height = int(str(self.sprite_height) + event.unicode)
                        self.load_spritesheet()
                        self.current_state_index = 0
                        self.current_sprite_index = 0
                elif active_text_box == 2:
                    self.sprite_entity.name += event.unicode
                elif active_text_box == 3:
                    self.sprite_entity.description += event.unicode
                elif active_text_box == 4:
                    self.sprite_entity.states[self.current_state_index].name += event.unicode
                elif active_text_box == 5:
                    self.sprite_entity.states[self.current_state_index].description += event.unicode
                elif active_text_box == 6:
                    self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].name += event.unicode
                elif active_text_box == 7:
                    self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].description += event.unicode
        return active_text_box

    def render_text_boxes(self, screen, text_boxes, active_text_box):
        font = pygame.font.Font(None, 24)
        for i, text_box in enumerate(text_boxes):
            if i == active_text_box:
                pygame.draw.rect(screen, (200, 200, 200), text_box)
            else:
                pygame.draw.rect(screen, (255, 255, 255), text_box)
            pygame.draw.rect(screen, (0, 0, 0), text_box, 2)
            if i == 0:
                text = str(self.sprite_width)
            elif i == 1:
                text = str(self.sprite_height)
            elif i == 2:
                text = self.sprite_entity.name if self.sprite_entity else ""
            elif i == 3:
                text = self.sprite_entity.description if self.sprite_entity else ""
            elif i == 4:
                text = self.sprite_entity.states[self.current_state_index].name if self.sprite_entity else ""
            elif i == 5:
                text = self.sprite_entity.states[self.current_state_index].description if self.sprite_entity else ""
            elif i == 6:
                text = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].name if self.sprite_entity else ""
            elif i == 7:
                text = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].description if self.sprite_entity else ""
            else:
                text = ""
            text_surface = font.render(text, True, (0, 0, 0))
            screen.blit(text_surface, (text_box.x + 5, text_box.y + 5))
    
    def render_navigation_buttons(self, screen):
        font = pygame.font.Font(None, 24)
        prev_text = font.render("Prev", True, (0, 0, 0))
        next_text = font.render("Next", True, (0, 0, 0))
        prev_rect = prev_text.get_rect(center=(screen.get_width() // 2 - 50, 20))
        next_rect = next_text.get_rect(center=(screen.get_width() // 2 + 50, 20))
        pygame.draw.rect(screen, (200, 200, 200), prev_rect.inflate(10, 10))
        pygame.draw.rect(screen, (200, 200, 200), next_rect.inflate(10, 10))
        screen.blit(prev_text, prev_rect)
        screen.blit(next_text, next_rect)
        return prev_rect, next_rect
        
    def save_sprite_entity(self):
        if self.sprite_entity is not None:
            base_folder = r"C:\Users\Tommaso\Documents\Dev\SpriteStash\out_sprites"
            sprite_name = self.sprite_entity.name
            folder_path = os.path.join(base_folder, sprite_name)
            self.sprite_entity.save_to_file(folder_path)
            print(f"Sprite entity saved to {folder_path}")
            print(self.sprite_entity)

    def load_sprite_entity(self):
        base_folder = r"C:\Users\Tommaso\Documents\Dev\SpriteStash\out_sprites"
        sprite_name = self.sprite_entity.name if self.sprite_entity else ""
        folder_path = os.path.join(base_folder, sprite_name, "metadata.json")
        if os.path.exists(folder_path):
            self.sprite_entity = SpriteEntity.load_from_file(folder_path)
            self.sprite_width = self.sprite_entity.sprite_width
            self.sprite_height = self.sprite_entity.sprite_height
            self.current_state_index = 0
            self.current_sprite_index = 0
            print(f"Sprite entity loaded from {folder_path}")
        else:
            print(f"No saved sprite entity found for {sprite_name}")

    @staticmethod
    def is_sprite_empty(sprite):
        return not bool(sprite.get_bounding_rect())



    
    def handle_mouse_events(self, event, screen, input_boxes, play_pause_button_rect, speed_control_rects, prev_button_rect, next_button_rect):
        clicked_input_box = None
        for input_box in input_boxes:
            if input_box.collidepoint(event.pos):
                clicked_input_box = input_box
                break
        
        if clicked_input_box is not None:
            return clicked_input_box
        else:
            if self.sprite_entity is not None:
                sprite_rects = self.render_spritesheet(screen, play_pause_button_rect)
                for sprite_rect, state_index, sprite_index in sprite_rects:
                    if sprite_rect.collidepoint(event.pos):
                        self.current_state_index = state_index
                        self.current_sprite_index = sprite_index
                        break
            
            if play_pause_button_rect is not None and play_pause_button_rect.collidepoint(event.pos):
                self.is_playing = not self.is_playing
            elif speed_control_rects is not None:
                minus_rect, plus_rect = speed_control_rects
                if minus_rect.collidepoint(event.pos):
                    self.speed = max(1, self.speed - 1)
                elif plus_rect.collidepoint(event.pos):
                    self.speed = min(10, self.speed + 1)
            
            if prev_button_rect is not None and prev_button_rect.collidepoint(event.pos):
                self.previous_spritesheet()
            elif next_button_rect is not None and next_button_rect.collidepoint(event.pos):
                self.next_spritesheet()
        
        return None

    def render_play_pause_button(self, screen, position):
        font = pygame.font.Font(None, 24)
        text = "Pause" if self.is_playing else "Play"
        text_surface = font.render(text, True, (0, 0, 0))
        text_rect = text_surface.get_rect(center=position)
        pygame.draw.rect(screen, (200, 200, 200), text_rect.inflate(20, 10))
        screen.blit(text_surface, text_rect)
        return text_rect

    def render_speed_control_buttons(self, screen, play_pause_button_rect):
        font = pygame.font.Font(None, 24)
        minus_text = font.render("-", True, (0, 0, 0))
        plus_text = font.render("+", True, (0, 0, 0))
        minus_rect = minus_text.get_rect(centerx=play_pause_button_rect.left - 30, centery=play_pause_button_rect.centery)
        plus_rect = plus_text.get_rect(centerx=play_pause_button_rect.right + 30, centery=play_pause_button_rect.centery)
        pygame.draw.rect(screen, (200, 200, 200), minus_rect.inflate(10, 10))
        pygame.draw.rect(screen, (200, 200, 200), plus_rect.inflate(10, 10))
        screen.blit(minus_text, minus_rect)
        screen.blit(plus_text, plus_rect)
        return minus_rect, plus_rect

    def render_text(self, screen):
        font = pygame.font.Font(None, 24)
        spritesheet_name = self.sprite_entity.source.split("\\")[-1]
        state_name = self.sprite_entity.states[self.current_state_index].name
        sprite_name = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].name
        sprite_description = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index].description
        state_index = self.current_state_index + 1
        frame_index = self.current_sprite_index + 1
        total_states = len(self.sprite_entity.states)
        total_frames = len(self.sprite_entity.states[self.current_state_index].sprites)
        text_lines = [
            f"Spritesheet: {spritesheet_name}",
            f"State: {state_name if state_name else 'Unnamed'} ({state_index}/{total_states})",
            f"Sprite: {sprite_name if sprite_name else 'Unnamed'} ({frame_index}/{total_frames})",
            f"Sprite Description: {sprite_description if sprite_description else 'No description'}",
            f"Sprite Size: {self.sprite_width}x{self.sprite_height}",
            f"Speed: {self.speed}"
        ]
        for i, line in enumerate(text_lines):
            text_surface = font.render(line, True, (0, 0, 0))
            screen.blit(text_surface, (10, 10 + i * 30))
        

    def render_error_message(self, screen, message):
        font = pygame.font.Font(None, 36)
        text_surface = font.render(message, True, (255, 0, 0))
        text_rect = text_surface.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
        screen.blit(text_surface, text_rect)



    def update(self, dt):
        if self.is_playing:
            self.frame_delay = 1 / (self.speed * 5)  # Adjust the frame delay based on the speed
            self.frame_timer += dt
            if self.frame_timer >= self.frame_delay:
                self.frame_timer = 0
                self.current_sprite_index = (self.current_sprite_index + 1) % len(self.sprite_entity.states[self.current_state_index].sprites)
                if self.current_sprite_index == 0:
                    self.current_state_index = (self.current_state_index + 1) % len(self.sprite_entity.states)

    def render_sprite(self, screen, sprite, position, size):
        visualization_scale = 2.0  # Adjust this value to control the visualization size
        scaled_size = (int(size[0] * visualization_scale), int(size[1] * visualization_scale))
        scaled_sprite = pygame.transform.scale(sprite.image, scaled_size)
        sprite_rect = scaled_sprite.get_rect(center=position)
        screen.blit(scaled_sprite, sprite_rect)
        return sprite_rect

    def render_spritesheet(self, screen, play_pause_button_rect):
        sprite_width, sprite_height = self.sprite_width, self.sprite_height
        max_sprites_per_row = max(len(state.sprites) for state in self.sprite_entity.states)
        
        target_width = int(screen.get_width() * 0.95)
        target_height = screen.get_height() - play_pause_button_rect.bottom - 40
        
        spritesheet_rows = len(self.sprite_entity.states)
        spritesheet_scale = min(
            target_width / (sprite_width * max_sprites_per_row),
            target_height / (sprite_height * spritesheet_rows)
        )
        
        scaled_sprite_width = int(sprite_width * spritesheet_scale)
        scaled_sprite_height = int(sprite_height * spritesheet_scale)
        
        total_width = scaled_sprite_width * max_sprites_per_row
        margin = max((screen.get_width() - total_width) // 2, int(screen.get_width() * 0.025))
        
        sprite_rects = []
        x = y = 0
        for state_index, state in enumerate(self.sprite_entity.states):
            for sprite_index, sprite in enumerate(state.sprites):
                sprite_position = (
                    x * scaled_sprite_width + margin,
                    y * scaled_sprite_height + play_pause_button_rect.bottom + 40
                )
                sprite_rect = pygame.Rect(
                    sprite_position[0],
                    sprite_position[1],
                    scaled_sprite_width,
                    scaled_sprite_height
                )
                scaled_sprite = pygame.transform.scale(sprite.image, (scaled_sprite_width, scaled_sprite_height))
                screen.blit(scaled_sprite, sprite_rect)
                sprite_rects.append((sprite_rect, state_index, sprite_index))
                
                if state_index == self.current_state_index and sprite_index == self.current_sprite_index:
                    border_rect = pygame.Rect(sprite_rect.left - 2, sprite_rect.top - 2, sprite_rect.width + 4, sprite_rect.height + 4)
                    pygame.draw.rect(screen, (255, 0, 0), border_rect, 2)
                
                x += 1
                if x >= len(state.sprites):
                    x = 0
                    y += 1
        
        return sprite_rects
    
    def render(self, screen):
        screen.fill((255, 255, 255))
        if self.sprite_entity is not None:
            if self.sprite_width > 0 and self.sprite_height > 0:
                if 0 <= self.current_state_index < len(self.sprite_entity.states) and \
                0 <= self.current_sprite_index < len(self.sprite_entity.states[self.current_state_index].sprites):
                    target_scale = min(screen.get_width() / (self.sprite_width * 5), screen.get_height() / (self.sprite_height * 5))
                    target_size = (int(self.sprite_width * target_scale), int(self.sprite_height * target_scale))
                    current_sprite = self.sprite_entity.states[self.current_state_index].sprites[self.current_sprite_index]
                    sprite_rect = self.render_sprite(screen, current_sprite, (screen.get_width() // 2, screen.get_height() // 4), target_size)
                    self.render_text(screen)
                    if sprite_rect is not None:
                        play_pause_button_rect = self.render_play_pause_button(screen, (screen.get_width() // 2, sprite_rect.bottom + 20))
                        speed_control_rects = self.render_speed_control_buttons(screen, play_pause_button_rect)
                        prev_button_rect, next_button_rect = self.render_navigation_buttons(screen)
                        self.render_spritesheet(screen, play_pause_button_rect)
                    else:
                        play_pause_button_rect = None
                        speed_control_rects = None
                        prev_button_rect = None
                        next_button_rect = None
                else:
                    self.render_error_message(screen, "Invalid state or sprite index.")
                    play_pause_button_rect = None
                    speed_control_rects = None
                    prev_button_rect = None
                    next_button_rect = None
            else:
                self.render_error_message(screen, "Invalid sprite size. Please enter valid dimensions.")
                play_pause_button_rect = None
                speed_control_rects = None
                prev_button_rect = None
                next_button_rect = None
        else:
            self.render_error_message(screen, "No sprite entity loaded. Press 'L' to load.")
            play_pause_button_rect = None
            speed_control_rects = None
            prev_button_rect = None
            next_button_rect = None
        return play_pause_button_rect, speed_control_rects, prev_button_rect, next_button_rect
    
def visualize_app(spritesheet_path, sprite_width, sprite_height, scale_factor=1.0):
    screen_width = 1920
    screen_height = 1000
    screen = pygame.display.set_mode((screen_width, screen_height))
    clock = pygame.time.Clock()
    sprite_manager = SpriteManager(spritesheet_path, sprite_width, sprite_height, scale_factor)
    input_box_width = pygame.Rect(screen_width - 610, 10, 200, 30)
    input_box_height = pygame.Rect(screen_width - 610, 50, 200, 30)
    entity_text_box = pygame.Rect(screen_width - 400, 10, 350, 30)
    entity_description_box = pygame.Rect(screen_width - 400, 50, 350, 100)
    state_text_box = pygame.Rect(screen_width - 400, 160, 350, 30)
    state_description_box = pygame.Rect(screen_width - 400, 200, 350, 100)
    sprite_name_box = pygame.Rect(screen_width - 400, 310, 350, 30)
    sprite_description_box = pygame.Rect(screen_width - 400, 350, 350, 100)
    text_boxes = [input_box_width, input_box_height, entity_text_box, entity_description_box, state_text_box, state_description_box, sprite_name_box, sprite_description_box]
    active_text_box = None
    play_pause_button_rect = None
    speed_control_rects = None
    prev_button_rect = None
    next_button_rect = None
    running = True
    while running:
        dt = clock.tick(60) / 1000  # Get the time since the last frame in seconds
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                active_text_box = sprite_manager.handle_key_events(event, active_text_box)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if sprite_manager.sprite_entity is not None:
                    sprite_manager.render_input_boxes(screen, text_boxes, active_text_box)

                    sprite_manager.handle_mouse_events(event, screen, text_boxes[:2], play_pause_button_rect, speed_control_rects, prev_button_rect, next_button_rect)
                clicked_text_box = False
                for i, text_box in enumerate(text_boxes):
                    if text_box.collidepoint(event.pos):
                        active_text_box = i
                        clicked_text_box = True
                        break
                if not clicked_text_box:
                    active_text_box = None
        sprite_manager.update(dt)
        if sprite_manager.sprite_entity is not None:
            play_pause_button_rect, speed_control_rects, prev_button_rect, next_button_rect = sprite_manager.render(screen)
        else:
            screen.fill((255, 255, 255))
            sprite_manager.render_error_message(screen, "No sprite entity loaded. Press 'L' to load.")
        sprite_manager.render_text_boxes(screen, text_boxes, active_text_box)
        pygame.display.flip()
    pygame.quit()

# Initialize Pygame
pygame.init()
# Set the display mode
screen_width = 1600
screen_height = 1000
pygame.display.set_mode((screen_width, screen_height))


#compose spritesheet_path with current_path + \raw_sprites\ + fire_FREE_SpriteSheet_288x128.png"
current_path = os.getcwd()
#use os to copose for safety
folder = os.path.join(current_path,"raw_sprites")
img_name = "fire_FREE_SpriteSheet_288x128.png"
spritesheet_path = os.path.join(folder,img_name)

sprite_width = 288
sprite_height = 128
visualize_app(spritesheet_path, sprite_width, sprite_height, scale_factor=0.2)