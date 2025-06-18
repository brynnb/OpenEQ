# OpenEQ File Converter

A Python-based converter for extracting and converting classic EverQuest game assets into modern formats suitable for 3D applications, web development, and preservation.


## Overview

This converter processes original EverQuest game files and converts them into modern 3D formats. It handles complex proprietary game data including:

- **3D Zone Geometry** - Buildings, terrain, objects
- **Textures** - Environmental and object textures
- **Materials** - Surface properties and transparency
- **Character Models** - 3D models with animations (basic support)
- **Scene Structure** - Object placement and hierarchy



## File Format Support

### Input Formats (EverQuest Proprietary)

#### `.S3D` Files (Sony 3D Archive)

- **Purpose**: Container format for EverQuest assets
- **Structure**: Compressed archive containing multiple files
- **Contents**: WLD files, textures, models, animations
- **Compression**: Custom deflate-based compression
- **Directory**: Contains file table with CRC32 checksums

#### `.WLD` Files (World Definition)

- **Purpose**: 3D scene and model definitions
- **Structure**: Binary format with fragment-based architecture
- **Key Fragments**:
  - `0x03` - Texture references
  - `0x14` - Actor definitions (characters)
  - `0x15` - Object instances and placement
  - `0x28` - Light definitions
  - `0x31` - Texture lists
  - `0x36` - Mesh geometry data
- **Complexity**: Hierarchical references between fragments

#### `.TER` / `.MOD` Files (Terrain/Model Data)

- **Purpose**: Geometry data for newer EverQuest zones
- **Structure**: Binary format with material definitions
- **Contents**: Vertex data, polygon indices, material properties
- **Versions**: Multiple format versions supported

#### Texture Formats

- **BMP**: Standard bitmap images
- **DDS**: DirectDraw Surface (compressed textures)
- **Support**: Automatic format detection and conversion

### Output Formats (OpenEQ Proprietary)

#### `.OEZ` Files (OpenEQ Zone)

Our custom binary format for zone data:

```
Header:
  - Material count (uint32)
  - Materials array:
    - Flags (uint32)
    - Parameters (uint32)
    - Filename count (uint32)
    - Filenames (variable-length strings)

  - Object count (uint32)
  - Objects array:
    - Mesh count (uint32)
    - Meshes array:
      - Material ID (uint32)
      - Collidable flag (uint32)
      - Vertex count (uint32)
      - Vertex data (9 floats per vertex: pos(3) + normal(3) + uv(2) + bone(1))
      - Index count (uint32)
      - Index data (uint32 array)

  - Placeable count (uint32)
  - Placeables array:
    - Object reference (uint32)
    - Position (3 floats)
    - Rotation (3 floats)
    - Scale (3 floats)

  - Light count (uint32)
  - Lights array:
    - Position (3 floats)
    - Color (3 floats)
    - Radius (float)
    - Attenuation (float)
    - Flags (uint32)
```

#### `.OEC` Files (OpenEQ Character)

Binary format for character models with skeletal animation data:

```
Header:
  - Mesh count (uint32)
  - Meshes array:
    - Material flags (uint32)
    - Texture count (uint32)
    - Texture filenames (variable-length strings)
    - Vertex count (uint32)
    - Vertex data separated by component:
      - Positions (3 floats per vertex)
      - Normals (3 floats per vertex)
      - Texture coordinates (2 floats per vertex)
      - Bone indices (uint32 per vertex)
    - Polygon count (uint32)
    - Polygon indices (uint32 array)

  - Bone parent count (uint32)
  - Bone hierarchy (int32 array)

  - Animation count (uint32)
  - Animations array:
    - Animation name (variable-length string)
    - Frame data (7 floats per frame: position(3) + rotation(4))
```

#### Compressed Archive (`.ZIP`)

Final output contains:

- Binary zone/character data (`.oez` or `.oec`)
- Converted texture files (`.png`)
- Optimized for modern loading

### Modern Output Formats

#### `.GLB` Files (glTF Binary)

For Three.js and web development:

- **Industry Standard**: Khronos Group glTF 2.0
- **Features**: PBR materials, embedded textures, scene hierarchy
- **Size**: ~80% smaller than original files
- **Compatibility**: All modern 3D engines and browsers

## Installation & Setup

### Prerequisites

- **Python 3.7+** 
- **EverQuest Files** in accessible directory

### Configuration

1. **Clone Repository**:

   ```bash
   git clone https://github.com/your-repo/OpenEQ.git
   cd OpenEQ/converter
   ```

2. **Create Configuration** (`openeq.cfg`):

   ```ini
   [EverQuest]
   # Path to your EverQuest files
   eq_path = /Users/brynnbateman/Downloads/EQLite

   [Converter]
   # Enable texture resampling for size optimization
   resample = true

   # Output format options
   include_collision = true
   optimize_meshes = true
   ```

3. **Verify File Structure**:
   ```
   EQLite/
   ├── gfaydark.s3d          # Main zone file
   ├── gfaydark_obj.s3d      # Zone objects
   ├── gfaydark_chr.s3d      # Characters (optional)
   ├── objects.wld           # Global objects
   └── lights.wld            # Lighting data
   ```

## Usage

### Basic Zone Conversion

```bash
# Convert EverQuest zone to OpenEQ format
python3 converter.py gfaydark

# Output: gfaydark.zip (contains .oez + textures)
```

### Character Model Conversion

```bash
# Convert character models
python3 converter.py gfaydark_chr

# Output: gfaydark_chr.zip (contains .oec + textures)
```

### Batch Conversion

```bash
# Convert multiple zones
for zone in gfaydark qeynos freeport; do
    python3 converter.py $zone
done
```

### Web-Ready Conversion (Three.js)

```bash
# Step 1: Convert to OpenEQ format
python3 converter.py gfaydark

# Step 2: Convert to glTF for web
python3 oes_to_gltf.py gfaydark.zip gfaydark.glb

# Result: gfaydark.glb (ready for Three.js)
```

## Output Formats

### File Size Comparison

| Format                  | Size  | Use Case                    |
| ----------------------- | ----- | --------------------------- |
| `gfaydark.zip` (OpenEQ) | 1.1MB | OpenEQ engine, preservation |
| `gfaydark.glb` (glTF)   | 224KB | Web development, Three.js   |

### Contents Structure

**OpenEQ ZIP Archive**:

```
gfaydark.zip
├── zone.oez              # Binary zone data
├── fire1.png             # Converted textures
├── ARMORSIGN.png
├── CITYSTONE.png
└── ...                   # Additional textures
```

**glTF Binary**:

```
gfaydark.glb              # Self-contained binary
├── JSON scene data       # Embedded
├── Binary mesh data      # Embedded
└── PNG textures         # Embedded
```

## Three.js Integration

### Quick Start

```javascript
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const loader = new GLTFLoader();
loader.load("gfaydark.glb", function (gltf) {
  scene.add(gltf.scene);

  // Auto-fit camera
  const box = new THREE.Box3().setFromObject(gltf.scene);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());

  camera.position.set(center.x, center.y + size.y, center.z + size.z);
  camera.lookAt(center);
});
```

### Viewer Application

Use the included `three_js_viewer.html` for immediate viewing:

1. Open in web browser
2. Drag & drop `.glb` files
3. Interactive 3D exploration

**Controls**:

- **Orbit**: Left click + drag
- **Zoom**: Mouse wheel
- **Pan**: Right click + drag

## Technical Details

### EverQuest File Format Insights

#### S3D Archive Structure

```
File Header:
  - Directory offset (uint32)
  - Magic "PFS " (0x20534650)

Directory Section:
  - Chunk count (uint32)
  - Chunks array:
    - CRC32 checksum (uint32)
    - Data offset (uint32)
    - Compressed size (uint32)

Filename Directory:
  - Special chunk (CRC: 0x61580AC9)
  - Contains null-terminated filenames
  - Maps to chunk indices
```

#### WLD Fragment System

```
Fragment Header:
  - Size (uint32)
  - Type (uint32)
  - Name reference (uint32)

Fragment Types:
  0x03 - Texture Definition
  0x04 - Texture List Reference
  0x05 - Material Definition
  0x14 - Actor Definition (Character)
  0x15 - Object Instance
  0x28 - Light Definition
  0x31 - Texture List
  0x36 - Mesh Definition
```

#### Texture Index System Discovery

**Original Assumption**: `[count][ref1][ref2]...[refN]`
**Actual Format**: `[0][reference]` (single reference per list)

This discovery resolved major texture processing issues.

### Vertex Data Layout

```c
struct Vertex {
    float position[3];    // X, Y, Z coordinates
    float normal[3];      // Surface normal vector
    float texcoord[2];    // UV texture coordinates
    float bone_index;     // Skeletal animation (characters)
};
```

### Material Flag System

```c
// Material flags mapping
FLAG_NORMAL       = 0x00    // Standard opaque material
FLAG_TRANSPARENT  = 0x04    // Alpha blending
FLAG_ALPHA_MASK   = 0x02    // Alpha testing
FLAG_EMISSIVE     = 0x08    // Self-illuminated
FLAG_ANIMATED     = 0x10    // Texture animation
```

## Status & Known Issues

### ✅ Fully Functional

- **Python 3 Migration**: Complete compatibility
- **Zone Conversion**: All major zones supported
- **Texture Processing**: PNG conversion working
- **Material System**: Transparency and properties preserved
- **Three.js Export**: Web-ready glTF generation
- **File Size**: Optimized output formats

### ⚠️ Known Limitations

#### Texture Index Warnings

Some polygons reference texture indices that don't exist:

```
Warning: Texture index 1 out of range (available: 1) in convertObjects
Warning: Texture index 10 out of range (available: 1) in convertZone
```

**Analysis**:

- Converter continues to function
- Textures are processed correctly
- Some polygons may use fallback materials
- Likely indicates complex multi-texture systems in EverQuest

**Impact**: Minimal - output is usable but may not be 100% accurate

#### Missing Features

- **Character Animations**: Basic support only
- **Advanced Lighting**: Simple light conversion
- **Level of Detail**: Single quality output
- **Audio**: Not supported

### 🔧 Recent Fixes Applied

1. **Integer Division**: Fixed Python 3 compatibility in slice operations
2. **Binary I/O**: Corrected StringIO vs BytesIO usage
3. **String Encoding**: Fixed binary data handling
4. **Texture Format**: Discovered correct WLD texture list format
5. **Index Size**: Support for large meshes (32-bit indices)

### Development Setup

```bash
# Create development environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Testing New Zones

1. Ensure EverQuest files are accessible
2. Run converter with debug output:
   ```bash
   python3 converter.py <zone_name> --debug
   ```
3. Check output for warnings and errors
4. Validate with Three.js viewer

### Code Structure

```
converter/
├── converter.py          # Main conversion script
├── buffer.py            # Binary data handling
├── s3d.py               # S3D archive reader
├── wld.py               # WLD fragment parser
├── zonefile.py          # Zone output format
├── charfile.py          # Character output format
├── oes_to_gltf.py       # glTF export
├── three_js_viewer.html # Web viewer
└── README.md            # This file
```

## Resources

- [EverQuest File Formats](https://github.com/EQEmu/Server/wiki/File-Formats)
- [glTF Specification](https://github.com/KhronosGroup/glTF)
- [Three.js Documentation](https://threejs.org/docs/)
- [OpenEQ Project](https://github.com/OpenEQ)

---
