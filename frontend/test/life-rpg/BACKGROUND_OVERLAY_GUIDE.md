# Background & Overlay Customization Guide

## How to Change the Detective Table Background

### Step 1: Add Your Image
1. Place your detective table PNG image in the `public` folder:
   ```
   frontend/test/life-rpg/public/detective-table.png
   ```

2. Or use any path relative to the public folder:
   - `/detective-table.png` (recommended)
   - `/images/detective-table.png`
   - Or use an external URL

### Step 2: Update the Image Path
Open `frontend/test/life-rpg/src/LifeRPGInterface.jsx` and find line ~249:

```jsx
backgroundImage: `url('/detective-table.png')`, // Change this path
```

**Options:**
- **Local file**: `url('/detective-table.png')` (must be in `public/` folder)
- **External URL**: `url('https://example.com/table.jpg')`
- **Relative path**: `url('/images/my-table.png')`

### Step 3: Resize the Background Image

You have several options to resize the background:

#### Option A: CSS Resizing (Recommended - No image editing needed)

In `LifeRPGInterface.jsx` around line 252, modify the `backgroundSize` property:

```jsx
backgroundSize: 'cover',  // Change this value
```

**Common size options:**
- `'cover'` - Scales image to cover entire screen (may crop edges)
- `'contain'` - Scales image to fit entire screen (may show empty space)
- `'100% 100%'` - Stretches image to exact screen size (may distort)
- `'1920px 1080px'` - Specific pixel dimensions
- `'auto'` - Uses image's natural size

**Custom sizing examples:**
```jsx
// Exact dimensions
backgroundSize: '1920px 1080px',

// Percentage of screen
backgroundSize: '120% 120%',  // Larger than screen
backgroundSize: '80% 80%',    // Smaller than screen

// Width only (height auto)
backgroundSize: '100% auto',

// Height only (width auto)
backgroundSize: 'auto 100%',
```

#### Option B: Reposition the Background

If the image is too large/small, you can also adjust its position:

```jsx
backgroundPosition: 'center',  // Change this
```

**Position options:**
- `'center'` - Centers the image
- `'top'`, `'bottom'`, `'left'`, `'right'` - Aligns to edge
- `'50% 30%'` - Custom position (horizontal%, vertical%)
- `'100px 200px'` - Pixel offset from top-left

**Examples:**
```jsx
// Show top-left portion of image
backgroundPosition: 'top left',

// Show bottom-right portion
backgroundPosition: 'bottom right',

// Custom offset
backgroundPosition: '20% 40%',  // 20% from left, 40% from top
```

#### Option C: Resize the Actual Image File

If you want to resize the PNG file itself:

1. **Using image editing software:**
   - Open `detective-table.png` in Photoshop, GIMP, or similar
   - Resize to your desired dimensions (e.g., 1920x1080 for Full HD)
   - Save and replace the file

2. **Using online tools:**
   - Upload to: https://www.iloveimg.com/resize-image
   - Set dimensions (e.g., 1920x1080)
   - Download and replace the file

3. **Recommended dimensions:**
   - **Desktop**: 1920x1080 (Full HD) or 2560x1440 (2K)
   - **Mobile**: 1080x1920 (portrait) or 1920x1080 (landscape)
   - **Large screens**: 3840x2160 (4K)

---

## How to Customize the Lighting Overlay Image

The lighting overlay is in `frontend/test/life-rpg/src/LifeRPGInterface.jsx` around line ~260.

### Step 1: Add Your Overlay Image
1. Place your lighting overlay PNG image in the `public` folder:
   ```
   frontend/test/life-rpg/public/lighting-overlay.png
   ```

2. Or use any path relative to the public folder:
   - `/lighting-overlay.png` (recommended)
   - `/images/lighting-overlay.png`
   - Or use an external URL

### Step 2: Update the Image Path
Open `frontend/test/life-rpg/src/LifeRPGInterface.jsx` and find line ~260:

```jsx
backgroundImage: `url('/lighting-overlay.png')`, // Change this path
```

**Options:**
- **Local file**: `url('/lighting-overlay.png')` (must be in `public/` folder)
- **External URL**: `url('https://example.com/overlay.jpg')`
- **Relative path**: `url('/images/my-overlay.png')`

### Step 3: Resize the Overlay Image

You have several options to resize the overlay:

#### Option A: CSS Resizing (Recommended - No image editing needed)

In `LifeRPGInterface.jsx` around line 264, modify the `backgroundSize` property:

```jsx
backgroundSize: 'cover',  // Change this value
```

**Common size options:**
- `'cover'` - Scales overlay to cover entire screen (may crop edges)
- `'contain'` - Scales overlay to fit entire screen (may show empty space)
- `'100% 100%'` - Stretches overlay to exact screen size (may distort)
- `'1920px 1080px'` - Specific pixel dimensions
- `'auto'` - Uses overlay's natural size

**Custom sizing examples:**
```jsx
// Exact dimensions
backgroundSize: '1920px 1080px',

// Percentage of screen
backgroundSize: '120% 120%',  // Larger than screen (may extend beyond)
backgroundSize: '80% 80%',    // Smaller than screen (may not cover fully)

// Match background exactly
backgroundSize: 'cover',  // Same as background

// Width only (height auto)
backgroundSize: '100% auto',

// Height only (width auto)
backgroundSize: 'auto 100%',
```

#### Option B: Reposition the Overlay

If the overlay doesn't align with your lighting, adjust its position:

```jsx
backgroundPosition: 'center',  // Change this
```

**Position options:**
- `'center'` - Centers the overlay
- `'top'`, `'bottom'`, `'left'`, `'right'` - Aligns to edge
- `'50% 30%'` - Custom position (horizontal%, vertical%)
- `'100px 200px'` - Pixel offset from top-left

**Examples:**
```jsx
// Align overlay to match light source direction
backgroundPosition: 'top left',    // If light comes from top-left
backgroundPosition: 'top right',   // If light comes from top-right
backgroundPosition: '20% 30%',     // Custom position
```

#### Option C: Resize the Actual Overlay Image File

If you want to resize the PNG file itself:

1. **Using image editing software:**
   - Open `lighting-overlay.png` in Photoshop, GIMP, or similar
   - Resize to match your background dimensions (e.g., 1920x1080)
   - Save and replace the file

2. **Using online tools:**
   - Upload to: https://www.iloveimg.com/resize-image
   - Set dimensions to match your background
   - Download and replace the file

3. **Recommended dimensions:**
   - **Match background size**: Use same dimensions as your table background
   - **Common sizes**: 1920x1080, 2560x1440, or 3840x2160

### Step 4: Adjust Other Overlay Settings

You can also customize these properties:

```jsx
mixBlendMode: 'overlay',  // Blend mode options (see below)
opacity: 0.6,             // Overall opacity (0.0 to 1.0)
```

**Blend Mode Options:**
- `'overlay'` - Default, creates a realistic lighting effect
- `'screen'` - Brightens the image (good for light overlays)
- `'soft-light'` - Subtle lighting effect
- `'multiply'` - Darkens (good for shadow overlays)
- `'normal'` - No blending, just overlays the image
- `'hard-light'` - Stronger contrast
- `'color-dodge'` - Very bright, dramatic effect

**Opacity Values:**
- `0.3` - Very subtle
- `0.6` - Default, balanced
- `0.9` - Strong effect
- `1.0` - Full intensity

**Background Size:**
- `'cover'` - Covers entire screen (recommended)
- `'contain'` - Fits entire image on screen
- `'100% 100%'` - Stretches to exact screen size
- `'1920px 1080px'` - Specific dimensions

**Background Position:**
- `'center'` - Centers the overlay
- `'top'`, `'bottom'`, `'left'`, `'right'` - Aligns to edge
- `'50% 30%'` - Custom position (horizontal, vertical)

---

## Testing Tips

1. **Use Browser DevTools**: Right-click → Inspect → Modify the overlay divs in real-time
2. **Adjust incrementally**: Change one value at a time to see the effect
3. **Check different screen sizes**: Test on mobile and desktop
4. **Match your table image**: Adjust lighting direction to match shadows in your table photo

---

## File Locations Summary

- **Background image**: `frontend/test/life-rpg/public/detective-table.png`
- **Overlay image**: `frontend/test/life-rpg/public/lighting-overlay.png`
- **Background code**: `frontend/test/life-rpg/src/LifeRPGInterface.jsx` (line ~249)
- **Overlay code**: `frontend/test/life-rpg/src/LifeRPGInterface.jsx` (line ~260)

## Quick Tips

1. **Test different blend modes**: The `mixBlendMode` property dramatically changes how the overlay looks
2. **Adjust opacity first**: Start with `opacity: 0.5` and increase/decrease to find the right balance
3. **Match your table image**: Position the overlay to match the lighting direction in your table photo
4. **Use DevTools**: Right-click → Inspect → Modify the overlay div in real-time to see changes instantly
5. **Match sizes**: For best results, make sure overlay and background use the same `backgroundSize` value
6. **Test on different screens**: Check how it looks on mobile, tablet, and desktop

## Common Resizing Scenarios

### Scenario 1: Background too large, showing wrong area
```jsx
// Solution: Use 'cover' and adjust position
backgroundSize: 'cover',
backgroundPosition: 'center',  // Or 'top', 'bottom', etc.
```

### Scenario 2: Background too small, showing empty space
```jsx
// Solution: Stretch to fill screen
backgroundSize: '100% 100%',
```

### Scenario 3: Overlay doesn't align with background
```jsx
// Solution: Match background size and position
backgroundSize: 'cover',  // Same as background
backgroundPosition: 'center',  // Same as background
```

### Scenario 4: Overlay too strong/weak
```jsx
// Solution: Adjust opacity
opacity: 0.4,  // Weaker effect
opacity: 0.8,  // Stronger effect
```

### Scenario 5: Need to crop/zoom into specific area
```jsx
// Solution: Use larger size and position
backgroundSize: '150% 150%',  // Zoom in
backgroundPosition: '30% 40%',  // Show specific area
```

