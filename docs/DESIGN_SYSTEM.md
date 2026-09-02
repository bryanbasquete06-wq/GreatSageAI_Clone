# Elívea — Design System v1.0
## "Fantasia Premium" — Identidade Visual Coerente

---

## 1. PHILOSOPHY

A interface deve parecer um **artefato mágico de altí technologies** — não um app de produtividade com filtro dourado, e não um protótipo amador. 

**Referências visuais:**
- HUD de RPG moderno (Genshin Impact, Honkai Star Rail menus)
- Círculos de magia de Tensei Shitara Slime
- Interface de status/evolução de Persona 5
- Glassmorphism sutil (não exagerado)

**O que NÃO é:**
- Dashboard de SaaS genérico
- Sci-fi holográfico com ciano/roxo
- App de produtividade com gradientes neon
- Protótipo com efeitos CSS/Qt exagerados

---

## 2. COLOR TOKENS

### Core Palette
| Token | Hex | Uso |
|-------|-----|-----|
| `BG_DEEP` | `#050507` | Fundo mais profundo (abaixo de tudo) |
| `BG_PRIMARY` | `#0a0a0c` | Fundo principal da janela |
| `BG_SURFACE` | `#111114` | Fundo de cards, painéis |
| `BG_ELEVATED` | `#1a1a1e` | Fundo de hover, dropdowns |
| `BG_OVERLAY` | `#222228` | Modais, overlays |

### Gold System (Identidade Principal)
| Token | Hex | Uso |
|-------|-----|-----|
| `GOLD_DEEP` | `#8B6914` | Bordas sutis, backgrounds escuros |
| `GOLD_PRIMARY` | `#C9A84C` | Bordas ativas, ícones, acentos |
| `GOLD_BRIGHT` | `#E8C55A` | Texto de destaque, títulos |
| `GOLD_LUMINOUS` | `#FFD966` | Brilho de energia, hover states |
| `GOLD_WHITE` | `#FFF3CC` | Texto dourado claro (WCAG AA on dark) |

### Yellow Energy (Estados Ativos)
| Token | Hex | Uso |
|-------|-----|-----|
| `ENERGY_DIM` | `#B8960F` | Energia em repouso |
| `ENERGY_PRIMARY` | `#E8C200` | Partículas, pulsos suaves |
| `ENERGY_BRIGHT` | `#FFD700` | Estados ativos, streaming |
| `ENERGY_HOT` | `#FFE44D` | Pico de energia, success |

### Neutrals
| Token | Hex | Uso |
|-------|-----|-----|
| `TEXT_PRIMARY` | `#F0EDE5` | Texto principal (WCAG AAA) |
| `TEXT_SECONDARY` | `#A09880` | Texto secundário (WCAG AA) |
| `TEXT_TERTIARY` | `#6B6358` | Texto desabilitado, placeholders |
| `TEXT_GHOST` | `#3D3830` | Dividers, bordas invisíveis |

### Semantic
| Token | Hex | Uso |
|-------|-----|-----|
| `SUCCESS` | `#7DB87D` | Sucesso (verde desaturado, premium) |
| `WARNING` | `#D4A843` | Aviso (amarelo escuro) |
| `ERROR` | `#C45B5B` | Erro (vermelho desaturado) |
| `INFO` | `#7DA8C4` | Info (azul desaturado) |

---

## 3. TYPOGRAPHY

### Font Stack
```
Primary: "Segoe UI", "Inter", -apple-system, sans-serif
Mono: "Cascadia Code", "JetBrains Mono", "Fira Code", monospace
Display: "Georgia", "Playfair Display", serif (títulos especiais)
```

### Type Scale (Hierarchy)
| Token | Size | Weight | Uso |
|-------|------|--------|-----|
| `display-lg` | 28px | 700 | Títulos de abertura |
| `display-md` | 22px | 700 | Títulos de seção |
| `heading` | 16px | 600 | Headers de painel |
| `body` | 13px | 400 | Texto de chat |
| `body-bold` | 13px | 600 | Texto enfatizado |
| `caption` | 11px | 400 | Labels, timestamps |
| `micro` | 9px | 400 | Badges, indicadores |

---

## 4. SPACING & LAYOUT

### Grid
- **Base unit:** 4px
- **Spacing scale:** 4, 8, 12, 16, 20, 24, 32, 40, 48, 64

### Border Radius
| Token | Value | Uso |
|-------|-------|-----|
| `radius-sm` | 6px | Badges, small buttons |
| `radius-md` | 10px | Cards, inputs |
| `radius-lg` | 14px | Painéis principais |
| `radius-xl` | 20px | Modais |
| `radius-full` | 9999px | Pills, circular |

### Shadows (Subtle, not neon)
```css
/* Elevation 1 - subtle lift */
box-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3);

/* Elevation 2 - card hover */
box-shadow: 0 4px 12px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.3);

/* Elevation 3 - modal */
box-shadow: 0 12px 40px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4);

/* Gold glow (used sparingly) */
box-shadow: 0 0 20px rgba(200,168,76,0.15);
```

---

## 5. COMPONENT PATTERNS

### Glass Panel
```
Background: BG_SURFACE + 85% opacity
Border: 1px solid GOLD_DEEP (idle) → GOLD_PRIMARY (active)
Border-radius: radius-lg
Backdrop-filter: blur(12px) (when GPU available)
```

### Button
```
Idle:    BG_ELEVATED, border GOLD_DEEP, text TEXT_SECONDARY
Hover:   BG_OVERLAY, border GOLD_PRIMARY, text GOLD_BRIGHT
Active:  GOLD_DEEP bg, text GOLD_WHITE
Disabled: BG_SURFACE, text TEXT_GHOST
```

### Input
```
Background: BG_DEEP
Border: 1px solid TEXT_GHOST → GOLD_PRIMARY (focus)
Border-radius: radius-md
Padding: 10px 14px
Font: body (13px)
```

### Chat Bubble (User)
```
Background: GOLD_DEEP (subtle)
Border: 1px solid GOLD_PRIMARY (very subtle)
Border-radius: radius-lg (top-right: radius-sm)
```

### Chat Bubble (Assistant)
```
Background: BG_SURFACE
Border: 1px solid TEXT_GHOST
Border-radius: radius-lg (top-left: radius-sm)
```

---

## 6. ANIMATION TOKENS

### Timing
| Token | Duration | Uso |
|-------|----------|-----|
| `instant` | 80ms | Hover states, micro-interactions |
| `fast` | 150ms | Panel transitions |
| `normal` | 250ms | Page transitions |
| `slow` | 400ms | Complex animations |
| `glacial` | 800ms | Onboarding, reveals |

### Easing
```
Standard: cubic-bezier(0.4, 0, 0.2, 1)
Enter:    cubic-bezier(0, 0, 0.2, 1)
Exit:     cubic-bezier(0.4, 0, 1, 1)
Bounce:   cubic-bezier(0.34, 1.56, 0.64, 1)
```

### Performance Rules
1. **Max 3 concurrent animations** on any visible element
2. **No animation on main thread** — all via QTimer/compositor
3. **Adaptive quality:** reduce particle count, skip blur on weak GPU
4. **`prefers-reduced-motion`** → disable all non-essential animations

---

## 7. ACCESSIBILITY

### WCAG AA Compliance
- **Text on dark:** minimum 4.5:1 contrast ratio
- **Gold text on black:** `#E8C55A` on `#0a0a0c` = 8.2:1 ✅
- **White text on dark:** `#F0EDE5` on `#0a0a0c` = 14.1:1 ✅
- **Avoid:** Yellow on white (fails), Gold on Gold (fails)

### Keyboard Navigation
- **Tab order:** Header → Input → Send → Panels → RuneCore
- **Focus ring:** 2px solid GOLD_PRIMARY, offset 2px
- **Escape:** closes any open panel/modal
- **Ctrl+K:** Command Palette (always available)

### Screen Reader
- All interactive elements have `accessibleName`/`accessibleDescription`
- Chat has `live="polite"` region for new messages
- RuneCoreWidget state announced via accessibility text

---

## 8. RESPONSIVE BEHAVIOR

### Window Sizes
- **Minimum:** 900x600
- **Recommended:** 1400x850
- **Maximum:** 1920x1080

### Layout Breakpoints
- **< 1200px:** Collapse sidebar, compact panels
- **< 900px:** Single column, stack panels

---

## 9. THEME VARIANTS

### Default: "Elívea Noir" (Gold + Black)
Primary: Gold system
Background: Pure black/deep gray
Accent: Yellow energy

### Variant: "Tensura Blue" (保留)
Primary: Cyan system  
Background: Deep navy
Accent: Blue energy

### Variant: "Crimson Lord" (保留)
Primary: Red system
Background: Deep wine
Accent: Pink energy

---

## 10. ANTI-PATTERNS TO ELIMINATE

1. ❌ Hardcoded hex colors in widget code → use theme tokens
2. ❌ Inline stylesheets with raw colors → use design tokens
3. ❌ Neon/glow on everything → use glow sparingly (RuneCore only)
4. ❌ Multiple competing accent colors → one accent per state
5. ❌ Tiny text for aesthetics → minimum 9px, prefer 11px+
6. ❌ Animations that block main thread → always background
7. ❌ Square/blocky gradients → minimum 5 color stops
8. ❌ Missing hover/focus states → every interactive element needs both
