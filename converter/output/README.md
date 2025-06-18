# OpenEQ GLB Output Files

This folder contains the converted GLB (binary glTF) files from OpenEQ zone data.

## Files

- **gfaydark.glb** - Greater Faydark zone converted to GLB format
  - **Size**: ~955KB
  - **Content**: Main terrain mesh with 21,088 vertices and 23,178 triangles
  - **Textures**: BMP textures converted to PNG format with proper material assignment
  - **Compatibility**: Can be viewed in Three.js, Blender, or any GLB-compatible viewer

## Usage

### Three.js

```javascript
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const loader = new GLTFLoader();
loader.load("gfaydark.glb", (gltf) => {
  scene.add(gltf.scene);
});
```

### Blender

File → Import → glTF 2.0 (.glb/.gltf) → Select gfaydark.glb

## Technical Details

- **Format**: GLB (binary glTF 2.0)
- **Vertex Data**: Position, Normal, UV coordinates
- **Textures**: PNG format embedded in GLB
- **Materials**: PBR materials with base color textures
- **Coordinate System**: OpenGL right-handed

## Generation

Generated using the OpenEQ Python converter:

```bash
python3 oes_to_gltf.py zone_name.zip output_name.glb
```

Files are automatically placed in this output folder.
