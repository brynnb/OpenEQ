#!/usr/bin/env python3
"""
Direct glTF export from OpenEQ Zone objects
Bypasses the intermediate .oez format for faster conversion

Coordinate System Transformation:
- EverQuest uses Z-up coordinate system (like 3ds Max, Blender)
- glTF uses Y-up coordinate system (industry standard)
- Transformation: (x, y, z) -> (x, z, -y) for positions and normals
"""

import json
import base64
import struct
import tempfile
from typing import Dict, List, Any, Optional, Tuple
import os
import sys
import io
from PIL import Image


def export_zone_to_gltf(zone, output_path: str, textures_dict: Dict[str, bytes] = None):
    """
    Export Zone object directly to glTF format without intermediate .oez step

    Args:
        zone: Zone object from zonefile.py
        output_path: Path for output .glb file
        textures_dict: Dictionary of texture name -> texture data
    """
    # First coalesce meshes like the original output method
    zone.coalesceObjectMeshes()

    # Collect all textures from materials
    if textures_dict is None:
        textures_dict = {}

    # Collect texture data from all materials
    for obj in zone.objects:
        for mesh in obj.meshes:
            material = mesh.material
            for i, filename in enumerate(material.filenames):
                if filename not in textures_dict and i < len(material.textures):
                    textures_dict[filename] = material.textures[i]

    # Create glTF structure
    gltf = {
        "asset": {"version": "2.0", "generator": "OpenEQ Direct Converter"},
        "scenes": [{"nodes": []}],
        "scene": 0,
        "nodes": [],
        "meshes": [],
        "materials": [],
        "textures": [],
        "images": [],
        "accessors": [],
        "bufferViews": [],
        "buffers": [],
    }

    # Binary data buffer
    binary_data = bytearray()

    # Process textures and images
    image_map = {}
    for texture_name, texture_data in textures_dict.items():
        # Convert texture to PNG if needed
        png_data = convert_texture_to_png(texture_data, texture_name)

        image_index = len(gltf["images"])
        image_map[texture_name] = image_index

        # Add to binary buffer
        buffer_view_index = len(gltf["bufferViews"])
        start_pos = len(binary_data)
        binary_data.extend(png_data)

        gltf["images"].append(
            {"mimeType": "image/png", "bufferView": buffer_view_index}
        )

        gltf["bufferViews"].append(
            {"buffer": 0, "byteOffset": start_pos, "byteLength": len(png_data)}
        )

        gltf["textures"].append({"source": image_index})

    # Process materials
    material_map = {}
    for obj in zone.objects:
        for mesh in obj.meshes:
            material = mesh.material
            mat_key = (material.flags, material.param, material.filenames)

            if mat_key not in material_map:
                mat_index = len(gltf["materials"])
                material_map[mat_key] = mat_index

                gltf_material = {
                    "name": f"Material_{mat_index}",
                    "pbrMetallicRoughness": {
                        "metallicFactor": 0.0,
                        "roughnessFactor": 1.0,
                    },
                }

                # Add main texture if available
                if material.filenames:
                    texture_name = material.filenames[0]
                    if texture_name in image_map:
                        texture_index = image_map[texture_name]
                        gltf_material["pbrMetallicRoughness"]["baseColorTexture"] = {
                            "index": texture_index
                        }

                # Handle transparency
                if material.flags & 0x4:  # Transparent flag
                    gltf_material["alphaMode"] = "BLEND"
                elif material.flags & 0x2:  # Alpha mask flag
                    gltf_material["alphaMode"] = "MASK"
                    gltf_material["alphaCutoff"] = 0.5

                gltf["materials"].append(gltf_material)

    # Process meshes and create nodes
    for obj_index, obj in enumerate(zone.objects):
        if not obj.meshes:
            continue

        # Create node for this object
        node_index = len(gltf["nodes"])
        gltf["scenes"][0]["nodes"].append(node_index)

        # Process meshes for this object
        gltf_mesh_primitives = []

        for mesh in obj.meshes:
            # Get vertex data
            vertices = mesh.vertbuffer.data
            num_vertices = len(mesh.vertbuffer)

            # Extract positions, normals, texcoords (8 floats per vertex)
            # Convert from EverQuest Z-up coordinate system to glTF Y-up coordinate system
            positions = []
            normals = []
            texcoords = []

            for i in range(num_vertices):
                base_idx = i * mesh.vertbuffer.stride

                # Original EQ coordinates (Z-up)
                x, y, z = vertices[base_idx : base_idx + 3]
                nx, ny, nz = vertices[base_idx + 3 : base_idx + 6]

                # Transform Z-up to Y-up: (x, y, z) -> (x, z, -y)
                positions.extend([x, z, -y])
                normals.extend([nx, nz, -ny])
                texcoords.extend(vertices[base_idx + 6 : base_idx + 8])

            # Convert polygons to indices
            indices = []
            for poly in mesh.polygons:
                indices.extend([poly[0], poly[2], poly[1]])  # Reverse winding

            # Add vertex data to binary buffer
            pos_buffer_start = len(binary_data)
            pos_data = struct.pack("<" + "f" * len(positions), *positions)
            binary_data.extend(pos_data)

            normal_buffer_start = len(binary_data)
            normal_data = struct.pack("<" + "f" * len(normals), *normals)
            binary_data.extend(normal_data)

            texcoord_buffer_start = len(binary_data)
            texcoord_data = struct.pack("<" + "f" * len(texcoords), *texcoords)
            binary_data.extend(texcoord_data)

            # Add index data to binary buffer
            index_buffer_start = len(binary_data)
            index_data = struct.pack("<" + "I" * len(indices), *indices)
            binary_data.extend(index_data)

            # Create buffer views
            pos_buffer_view = len(gltf["bufferViews"])
            gltf["bufferViews"].append(
                {
                    "buffer": 0,
                    "byteOffset": pos_buffer_start,
                    "byteLength": len(pos_data),
                    "target": 34962,  # ARRAY_BUFFER
                }
            )

            normal_buffer_view = len(gltf["bufferViews"])
            gltf["bufferViews"].append(
                {
                    "buffer": 0,
                    "byteOffset": normal_buffer_start,
                    "byteLength": len(normal_data),
                    "target": 34962,  # ARRAY_BUFFER
                }
            )

            texcoord_buffer_view = len(gltf["bufferViews"])
            gltf["bufferViews"].append(
                {
                    "buffer": 0,
                    "byteOffset": texcoord_buffer_start,
                    "byteLength": len(texcoord_data),
                    "target": 34962,  # ARRAY_BUFFER
                }
            )

            index_buffer_view = len(gltf["bufferViews"])
            gltf["bufferViews"].append(
                {
                    "buffer": 0,
                    "byteOffset": index_buffer_start,
                    "byteLength": len(index_data),
                    "target": 34963,  # ELEMENT_ARRAY_BUFFER
                }
            )

            # Create accessors
            pos_accessor = len(gltf["accessors"])
            gltf["accessors"].append(
                {
                    "bufferView": pos_buffer_view,
                    "componentType": 5126,  # FLOAT
                    "count": num_vertices,
                    "type": "VEC3",
                    "min": [min(positions[i::3]) for i in range(3)],
                    "max": [max(positions[i::3]) for i in range(3)],
                }
            )

            normal_accessor = len(gltf["accessors"])
            gltf["accessors"].append(
                {
                    "bufferView": normal_buffer_view,
                    "componentType": 5126,  # FLOAT
                    "count": num_vertices,
                    "type": "VEC3",
                }
            )

            texcoord_accessor = len(gltf["accessors"])
            gltf["accessors"].append(
                {
                    "bufferView": texcoord_buffer_view,
                    "componentType": 5126,  # FLOAT
                    "count": num_vertices,
                    "type": "VEC2",
                }
            )

            index_accessor = len(gltf["accessors"])
            gltf["accessors"].append(
                {
                    "bufferView": index_buffer_view,
                    "componentType": 5125,  # UNSIGNED_INT
                    "count": len(indices),
                    "type": "SCALAR",
                }
            )

            # Create primitive
            mat_key = (
                mesh.material.flags,
                mesh.material.param,
                mesh.material.filenames,
            )
            material_index = material_map[mat_key]

            primitive = {
                "attributes": {
                    "POSITION": pos_accessor,
                    "NORMAL": normal_accessor,
                    "TEXCOORD_0": texcoord_accessor,
                },
                "indices": index_accessor,
                "material": material_index,
            }

            gltf_mesh_primitives.append(primitive)

        # Create glTF mesh
        if gltf_mesh_primitives:
            mesh_index = len(gltf["meshes"])
            gltf["meshes"].append(
                {
                    "name": obj.name or f"Object_{obj_index}",
                    "primitives": gltf_mesh_primitives,
                }
            )

            # Create node
            gltf["nodes"].append(
                {
                    "name": obj.name or f"Node_{obj_index}",
                    "mesh": mesh_index,
                }
            )

    # Add buffer
    gltf["buffers"].append({"byteLength": len(binary_data)})

    # Write GLB file
    write_glb(gltf, binary_data, output_path)
    print(f"Exported glTF to: {output_path}")


def convert_texture_to_png(texture_data: bytes, texture_name: str) -> bytes:
    """Convert texture data to PNG format"""
    try:
        # Try to open as image
        image = Image.open(io.BytesIO(texture_data))

        # Convert to RGBA if needed
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

        # Save as PNG
        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")
        return png_buffer.getvalue()

    except Exception as e:
        print(f"Warning: Failed to convert texture {texture_name}: {e}")
        # Create gray placeholder
        placeholder = Image.new("RGBA", (64, 64), (128, 128, 128, 255))
        png_buffer = io.BytesIO()
        placeholder.save(png_buffer, format="PNG")
        return png_buffer.getvalue()


def write_glb(gltf: Dict[str, Any], binary_data: bytearray, output_path: str):
    """Write glTF data as GLB binary file"""

    # Convert glTF to JSON bytes
    json_data = json.dumps(gltf, separators=(",", ":")).encode("utf-8")

    # Pad JSON to 4-byte boundary
    json_padding = (4 - (len(json_data) % 4)) % 4
    json_data += b" " * json_padding

    # Pad binary data to 4-byte boundary
    bin_padding = (4 - (len(binary_data) % 4)) % 4
    binary_data.extend(b"\x00" * bin_padding)

    # Calculate sizes
    json_chunk_size = len(json_data)
    bin_chunk_size = len(binary_data)
    total_size = 12 + 8 + json_chunk_size + 8 + bin_chunk_size

    with open(output_path, "wb") as f:
        # GLB header
        f.write(b"glTF")  # Magic
        f.write(struct.pack("<I", 2))  # Version
        f.write(struct.pack("<I", total_size))  # Total length

        # JSON chunk
        f.write(struct.pack("<I", json_chunk_size))  # Chunk length
        f.write(b"JSON")  # Chunk type
        f.write(json_data)

        # Binary chunk
        f.write(struct.pack("<I", bin_chunk_size))  # Chunk length
        f.write(b"BIN\x00")  # Chunk type
        f.write(binary_data)
