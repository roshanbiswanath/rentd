---
name: Reliable Habitats
colors:
  surface: '#f7fafc'
  surface-dim: '#d7dadd'
  surface-bright: '#f7fafc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f4f6'
  surface-container: '#ebeef0'
  surface-container-high: '#e6e8eb'
  surface-container-highest: '#e0e3e5'
  on-surface: '#181c1e'
  on-surface-variant: '#3f484c'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eef1f3'
  outline: '#6f787d'
  outline-variant: '#bec8cd'
  surface-tint: '#006781'
  primary: '#005a71'
  on-primary: '#ffffff'
  primary-container: '#0e7490'
  on-primary-container: '#d3f1ff'
  inverse-primary: '#81d1f0'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#505355'
  on-tertiary: '#ffffff'
  tertiary-container: '#686b6d'
  on-tertiary-container: '#eaecee'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b9eaff'
  primary-fixed-dim: '#81d1f0'
  on-primary-fixed: '#001f29'
  on-primary-fixed-variant: '#004d62'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#e0e3e5'
  tertiary-fixed-dim: '#c4c7c9'
  on-tertiary-fixed: '#191c1e'
  on-tertiary-fixed-variant: '#444749'
  background: '#f7fafc'
  on-background: '#181c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Manrope
    fontSize: 48px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-h1:
    fontFamily: Manrope
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-h2:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-base:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-sm:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-bold:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1.4'
    letterSpacing: 0.05em
  label-subtle:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.4'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base-unit: 8px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 64px
  stack-xs: 4px
  stack-sm: 12px
  stack-md: 24px
  stack-lg: 48px
---

## Brand & Style

The core philosophy of this design system is "Data Confidence." In the high-stakes world of property rentals, users require a sense of absolute reliability and clarity. The aesthetic follows a **Corporate/Modern** movement, blending clinical precision with high-end editorial whitespace.

The brand personality is authoritative yet accessible, positioning itself as a sophisticated facilitator rather than a mere listing site. The visual language favors organization over decoration, ensuring that property details and contractual information remain the primary focus. This design system evokes an emotional response of security, efficiency, and professional transparency.

## Colors

The palette is anchored by a professional **Teal**, chosen for its psychological association with clarity, growth, and trust. This primary color is used strategically for calls to action and key brand touchpoints to maintain its impact. 

A sophisticated range of "Slate" grays provides the structural framework, moving away from pure blacks to softer, more modern neutrals. High-contrast status colors are employed to provide immediate "data confidence"—green for verified listings, amber for pending applications, and red for urgent alerts. This design system relies on a "High-Light" approach, using plenty of white space and subtle gray backgrounds to define content zones without using heavy lines.

## Typography

This design system utilizes **Manrope** for its balance of geometric modernism and exceptional legibility. The typeface's open counters and clean terminals ensure that even dense lease agreements or financial tables remain easy to scan.

The typographic hierarchy is strictly enforced. Display sizes use a heavier weight and tighter letter-spacing for a bold, confident look. Body copy utilizes a generous line-height (1.6) to prevent eye fatigue during long reading sessions. Labels utilize uppercase styling with increased tracking to differentiate metadata from primary content.

## Layout & Spacing

This design system is built on a **Fixed Grid** model for desktop to ensure content remains readable on ultra-wide monitors, transitioning to a fluid layout for mobile devices. It utilizes a 12-column grid with a 24px gutter to facilitate complex dashboard layouts and side-by-side property comparisons.

A strict 8px spatial rhythm governs all padding and margins. Vertical rhythm is established through "stack" variables, ensuring that the distance between a property title and its description is consistently tighter than the distance between separate property cards.

## Elevation & Depth

Visual hierarchy is established through **Ambient Shadows** and **Tonal Layers**. Rather than using high-contrast borders, this design system uses soft, diffused shadows with a slight teal tint to lift active elements off the background.

1.  **Level 0 (Surface):** The primary background, usually off-white or light gray.
2.  **Level 1 (Card):** White surfaces with a 1px subtle gray border and no shadow, used for static content.
3.  **Level 2 (Interactive):** White surfaces with a soft, 12px blur shadow, used for clickable cards and hover states.
4.  **Level 3 (Overlay):** High-elevation surfaces with a 24px blur shadow and a backdrop blur (glassmorphism) behind them, used for modals and navigation menus.

## Shapes

The shape language of this design system is characterized by **Rounded** corners (Level 2). A base radius of 8px (0.5rem) is applied to all primary UI elements, including input fields and buttons. 

Larger containers, such as property image galleries or feature cards, utilize 16px (1rem) or 24px (1.5rem) radii to feel more inviting. This soft-rounding strategy balances the "trust" of a corporate grid with a contemporary, approachable feel, avoiding the harshness of sharp corners or the playfulness of full pill-shapes.

## Components

**Buttons**  
Primary buttons feature a solid teal background with white text. Secondary buttons use a teal outline with a subtle gray background on hover. All buttons utilize the base 8px roundedness.

**Input Fields**  
Fields are framed by a 1px slate-200 border. On focus, the border transitions to the primary teal with a subtle 3px outer glow (ring). Error states must clearly highlight the border in red and include a small descriptive icon.

**Cards**  
Property cards are the core of this design system. They feature a white background, a 16px corner radius, and a transition to a Level 2 shadow on hover. Content within cards is divided by subtle 1px horizontal dividers.

**Status Chips**  
Small, rounded-full indicators used for "Available," "Leased," or "Verified." These use a low-opacity version of the status color for the background and a high-opacity version for the text to ensure accessibility.

**Data Indicators**  
To reinforce the "Reliable" vibe, use progress bars for application completion and small "Confidence Scores" (numerical or star-based) next to landlord profiles, styled with clean, small labels.