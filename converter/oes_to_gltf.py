#!/usr/bin/env python3
"""
Convert OpenEQ zone files to glTF format for Three.js
Author: OpenEQ Converter
"""

import json
import base64
import struct
import tempfile
import zipfile
from typing import Dict, List, Any, Optional, Tuple
import os
import sys
import io
from PIL import Image


def read_zone_file(zone_zip_path: str) -> Dict[str, Any]:
    """
    Read and parse OpenEQ zone .zip file
    Returns parsed zone data structure
    """
    zone_data = {
        "materials": [],
        "objects": [],
        "placeables": [],
        "lights": [],
        "textures": {},
    }

    with zipfile.ZipFile(zone_zip_path, "r") as zip_file:
        # Read the zone.oez file
        if "zone.oez" in zip_file.namelist():
            zone_binary = zip_file.read("zone.oez")
            zone_data.update(parse_zone_binary(zone_binary))

            # Extract all texture files
        for filename in zip_file.namelist():
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".dds")):
                raw_data = zip_file.read(filename)

                # PNG files can be used directly
                if filename.lower().endswith(".png"):
                    zone_data["textures"][filename] = raw_data
                    print(f"Using PNG texture: {filename}")

                # Convert other formats to PNG for web compatibility
                elif filename.lower().endswith((".jpg", ".jpeg", ".bmp")):
                    try:
                        # Convert to PNG
                        image = Image.open(io.BytesIO(raw_data))

                        png_buffer = io.BytesIO()
                        # Convert to RGBA if needed
                        if image.mode not in ("RGB", "RGBA"):
                            image = image.convert("RGBA")

                        image.save(png_buffer, format="PNG")
                        png_data = png_buffer.getvalue()

                        # Use PNG data and change extension
                        png_filename = filename.rsplit(".", 1)[0] + ".png"
                        zone_data["textures"][png_filename] = png_data
                        print(
                            f"Converted {filename} -> {png_filename} ({len(raw_data)} -> {len(png_data)} bytes)"
                        )

                    except Exception as e:
                        print(f"Warning: Failed to convert {filename}: {e}")
                        # Keep original data as fallback
                        zone_data["textures"][filename] = raw_data

                # For DDS files - detect actual format and convert
                elif filename.lower().endswith(".dds"):
                    try:
                        # Check if it's actually BMP data with DDS extension
                        if len(raw_data) >= 2 and raw_data[0:2] == b"BM":
                            # It's actually BMP - convert to PNG
                            image = Image.open(io.BytesIO(raw_data))

                            png_buffer = io.BytesIO()
                            # Convert to RGBA if needed
                            if image.mode not in ("RGB", "RGBA"):
                                image = image.convert("RGBA")

                            image.save(png_buffer, format="PNG")
                            png_data = png_buffer.getvalue()

                            # Store as PNG with original filename (change extension)
                            png_filename = filename.rsplit(".", 1)[0] + ".png"
                            zone_data["textures"][png_filename] = png_data
                            print(
                                f"Converted BMP as DDS: {filename} -> {png_filename} ({len(raw_data)} -> {len(png_data)} bytes)"
                            )

                        elif len(raw_data) >= 4 and raw_data[0:4] == b"DDS ":
                            # Actually DDS format - try to process
                            print(
                                f"Warning: Actual DDS file found: {filename} - creating placeholder"
                            )
                            # Create yellow placeholder for now
                            placeholder = Image.new(
                                "RGBA", (64, 64), (255, 255, 0, 255)
                            )
                            png_buffer = io.BytesIO()
                            placeholder.save(png_buffer, format="PNG")
                            png_data = png_buffer.getvalue()

                            png_filename = filename.rsplit(".", 1)[0] + ".png"
                            zone_data["textures"][png_filename] = png_data
                            print(
                                f"Created placeholder for DDS: {filename} -> {png_filename}"
                            )

                        else:
                            # Try to open as BMP regardless of header (some files may have corrupted headers)
                            try:
                                image = Image.open(io.BytesIO(raw_data))

                                png_buffer = io.BytesIO()
                                # Convert to RGBA if needed
                                if image.mode not in ("RGB", "RGBA"):
                                    image = image.convert("RGBA")

                                image.save(png_buffer, format="PNG")
                                png_data = png_buffer.getvalue()

                                png_filename = filename.rsplit(".", 1)[0] + ".png"
                                zone_data["textures"][png_filename] = png_data
                                print(
                                    f"Converted unknown format as image: {filename} -> {png_filename} ({len(raw_data)} -> {len(png_data)} bytes)"
                                )
                            except Exception:
                                # Create a neutral placeholder instead of bright magenta
                                print(
                                    f"Warning: Could not process texture {filename} - creating neutral placeholder"
                                )
                                placeholder = Image.new(
                                    "RGBA", (64, 64), (128, 128, 128, 255)
                                )  # Gray
                                png_buffer = io.BytesIO()
                                placeholder.save(png_buffer, format="PNG")
                                png_data = png_buffer.getvalue()

                                png_filename = filename.rsplit(".", 1)[0] + ".png"
                                zone_data["textures"][png_filename] = png_data
                                print(
                                    f"Created neutral placeholder for {filename} -> {png_filename}"
                                )

                    except Exception as e:
                        print(f"Warning: Failed to process {filename}: {e}")
                        # Create red error placeholder
                        placeholder = Image.new(
                            "RGBA", (64, 64), (255, 0, 0, 255)
                        )  # Red
                        png_buffer = io.BytesIO()
                        placeholder.save(png_buffer, format="PNG")
                        png_data = png_buffer.getvalue()

                        png_filename = filename.rsplit(".", 1)[0] + ".png"
                        zone_data["textures"][png_filename] = png_data
                        print(
                            f"Created error placeholder for {filename} -> {png_filename}"
                        )

    return zone_data


def parse_zone_binary(data: bytes) -> Dict[str, Any]:
    """
    Parse the binary zone.oez format
    Based on zonefile.py output format
    FIXED: Correctly handle polygon count vs index count
    """
    result = {"materials": [], "objects": [], "placeables": [], "lights": []}

    pos = 0

    # Read materials
    if pos + 4 <= len(data):
        num_materials = struct.unpack("<I", data[pos : pos + 4])[0]
        pos += 4
        print(f"Reading {num_materials} materials")

        for i in range(num_materials):
            if pos + 12 <= len(data):
                flags, param, num_filenames = struct.unpack(
                    "<III", data[pos : pos + 12]
                )
                pos += 12

                filenames = []
                for j in range(num_filenames):
                    # Read string length (variable length encoding)
                    strlen = 0
                    shift = 0
                    while pos < len(data):
                        byte = data[pos]
                        pos += 1
                        strlen |= (byte & 0x7F) << shift
                        if (byte & 0x80) == 0:
                            break
                        shift += 7

                    if strlen > 0 and pos + strlen <= len(data):
                        filename = data[pos : pos + strlen].decode("utf-8")
                        filenames.append(filename)
                        pos += strlen

                result["materials"].append(
                    {"flags": flags, "param": param, "filenames": filenames}
                )

    # Read objects
    if pos + 4 <= len(data):
        num_objects = struct.unpack("<I", data[pos : pos + 4])[0]
        pos += 4
        print(f"Reading {num_objects} objects")

        # Statistics tracking
        stats = {
            "meshes_processed": 0,
            "meshes_successful": 0,
            "vertex_data_errors": 0,
            "index_data_errors": 0,
            "index_range_warnings": 0,
            "corrupted_meshes": 0,
            "total_vertices": 0,
            "total_indices": 0,
        }

        for i in range(num_objects):
            if pos + 4 <= len(data):
                num_meshes = struct.unpack("<I", data[pos : pos + 4])[0]
                pos += 4

                # Only show progress for objects with reasonable mesh counts
                if num_meshes < 10000:
                    print(f"  Object {i}: {num_meshes} meshes")
                else:
                    print(
                        f"  Object {i}: {num_meshes} meshes - WARNING: Suspicious count!"
                    )

                meshes = []
                for j in range(num_meshes):
                    stats["meshes_processed"] += 1

                    if pos + 16 <= len(data):
                        mat_id, collidable, num_verts, num_polygons = struct.unpack(
                            "<IIII", data[pos : pos + 16]
                        )
                        pos += 16

                        # Each polygon has 3 indices
                        num_indices = num_polygons * 3

                        # Check for corrupted mesh data (unreasonable vertex/polygon counts)
                        if num_verts > 100000 or num_polygons > 100000:
                            stats["corrupted_meshes"] += 1
                            print(
                                f"    Object {i} has corrupted mesh data - skipping remaining meshes"
                            )
                            # Break out of this object's mesh loop and continue to next object
                            break

                        # Read vertex data (8 floats per vertex: pos(3) + normal(3) + uv(2))
                        vert_data_size = num_verts * 8 * 4  # 8 floats * 4 bytes each
                        if pos + vert_data_size <= len(data):
                            vertices = struct.unpack(
                                "<" + "f" * (num_verts * 8),
                                data[pos : pos + vert_data_size],
                            )
                            pos += vert_data_size
                        else:
                            stats["vertex_data_errors"] += 1
                            vertices = []

                        # Read index data
                        index_data_size = num_indices * 4  # uint32 per index
                        if pos + index_data_size <= len(data):
                            indices = struct.unpack(
                                "<" + "I" * num_indices,
                                data[pos : pos + index_data_size],
                            )
                            pos += index_data_size

                            # Basic index validation - be more permissive
                            if indices:
                                max_index = max(indices)
                                if max_index >= num_verts:
                                    stats["index_range_warnings"] += 1
                                    # Try to fix indices instead of skipping
                                    indices = [
                                        (
                                            min(idx, num_verts - 1)
                                            if idx >= num_verts
                                            else idx
                                        )
                                        for idx in indices
                                    ]
                        else:
                            stats["index_data_errors"] += 1
                            indices = []
                            # Still need to advance position even if we can't read the data
                            pos = min(pos + index_data_size, len(data))

                        # Track successful mesh
                        if vertices is not None and indices is not None:
                            stats["meshes_successful"] += 1
                            stats["total_vertices"] += num_verts
                            stats["total_indices"] += num_indices

                            meshes.append(
                                {
                                    "material_id": mat_id,
                                    "collidable": collidable,
                                    "vertices": vertices,
                                    "indices": indices,
                                }
                            )

                result["objects"].append({"meshes": meshes})

        # Print summary statistics
        print(f"\nMesh Processing Summary:")
        print(f"  Successful meshes: {stats['meshes_successful']:,}")
        if stats["corrupted_meshes"] > 0:
            print(f"  Corrupted objects skipped: {stats['corrupted_meshes']:,}")
        print(f"  Total vertices: {stats['total_vertices']:,}")
        print(f"  Total triangles: {stats['total_indices'] // 3:,}")

    return result


def create_gltf_from_zone(zone_data: Dict[str, Any], output_path: str):
    """
    Convert zone data to glTF format
    """
    gltf = {
        "asset": {"version": "2.0", "generator": "OpenEQ Zone Converter - FIXED"},
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
    for texture_name, texture_data in zone_data["textures"].items():
        image_index = len(gltf["images"])
        image_map[texture_name] = image_index

        # Add to binary buffer
        buffer_view_index = len(gltf["bufferViews"])
        start_pos = len(binary_data)
        binary_data.extend(texture_data)

        gltf["images"].append(
            {"mimeType": "image/png", "bufferView": buffer_view_index}
        )

        gltf["bufferViews"].append(
            {"buffer": 0, "byteOffset": start_pos, "byteLength": len(texture_data)}
        )

        gltf["textures"].append({"source": image_index})

    # Process materials
    for i, material in enumerate(zone_data["materials"]):
        gltf_material = {
            "name": f"Material_{i}",
            "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0},
        }

        # Add main texture if available
        if material["filenames"]:
            texture_name = material["filenames"][0]

            # Try multiple texture name variations
            # Try different filename variations - prioritize PNG conversions
            possible_names = []

            # If it's a DDS file, try PNG version first (since we convert BMP->PNG)
            if texture_name.lower().endswith(".dds"):
                png_name = texture_name.rsplit(".", 1)[0] + ".png"
                possible_names.append(png_name)
                possible_names.append(texture_name)
            elif texture_name.lower().endswith(".bmp"):
                png_name = texture_name.rsplit(".", 1)[0] + ".png"
                possible_names.append(png_name)
                possible_names.append(texture_name)
            else:
                possible_names.append(texture_name)
                # Also try with PNG extension as fallback
                possible_names.append(texture_name.rsplit(".", 1)[0] + ".png")

            # Find matching texture
            found_texture = None
            for name in possible_names:
                if name in image_map:
                    found_texture = name
                    break

            if found_texture:
                texture_index = image_map[found_texture]
                gltf_material["pbrMetallicRoughness"]["baseColorTexture"] = {
                    "index": texture_index
                }
                print(f"Material {i} assigned texture: {found_texture}")
            else:
                print(f"Warning: Material {i} texture not found: {texture_name}")
                print(f"  Tried names: {possible_names}")
                print(
                    f"  Available textures: {list(image_map.keys())[:5]}..."
                )  # Show first 5

        # Handle transparency
        if material["flags"] & 0x4:  # Transparent flag
            gltf_material["alphaMode"] = "BLEND"
        elif material["flags"] & 0x2:  # Alpha mask flag
            gltf_material["alphaMode"] = "MASK"
            gltf_material["alphaCutoff"] = 0.5

        gltf["materials"].append(gltf_material)

    # Process meshes and objects
    for obj_index, obj in enumerate(zone_data["objects"]):
        for mesh_index, mesh in enumerate(obj["meshes"]):
            # Skip meshes with no data
            if not mesh["vertices"] or not mesh["indices"]:
                continue

            # Process vertices (position, normal, texcoord)
            vertices = mesh["vertices"]
            num_vertices = len(vertices) // 8

            positions = []
            normals = []
            texcoords = []

            for i in range(num_vertices):
                base_idx = i * 8
                positions.extend(vertices[base_idx : base_idx + 3])
                normals.extend(vertices[base_idx + 3 : base_idx + 6])
                texcoords.extend(vertices[base_idx + 6 : base_idx + 8])

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
            index_data = struct.pack("<" + "I" * len(mesh["indices"]), *mesh["indices"])
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
                    "count": len(mesh["indices"]),
                    "type": "SCALAR",
                }
            )

            # Create mesh
            gltf_mesh_index = len(gltf["meshes"])
            gltf["meshes"].append(
                {
                    "name": f"Object_{obj_index}_Mesh_{mesh_index}",
                    "primitives": [
                        {
                            "attributes": {
                                "POSITION": pos_accessor,
                                "NORMAL": normal_accessor,
                                "TEXCOORD_0": texcoord_accessor,
                            },
                            "indices": index_accessor,
                            "material": (
                                mesh["material_id"]
                                if mesh["material_id"] < len(gltf["materials"])
                                else 0
                            ),
                        }
                    ],
                }
            )

            # Create node
            node_index = len(gltf["nodes"])
            gltf["nodes"].append(
                {
                    "name": f"Object_{obj_index}_Node_{mesh_index}",
                    "mesh": gltf_mesh_index,
                }
            )

            # Add to scene
            gltf["scenes"][0]["nodes"].append(node_index)

    # Add the main buffer
    gltf["buffers"].append({"byteLength": len(binary_data)})

    # Write GLB file
    write_glb(gltf, binary_data, output_path)


def write_glb(gltf: Dict[str, Any], binary_data: bytearray, output_path: str):
    """
    Write glTF data as GLB (binary glTF) file
    """
    # Convert glTF to JSON
    json_data = json.dumps(gltf, separators=(",", ":")).encode("utf-8")

    # Pad JSON to 4-byte boundary
    json_padding = (4 - len(json_data) % 4) % 4
    json_data += b" " * json_padding

    # Pad binary data to 4-byte boundary
    binary_padding = (4 - len(binary_data) % 4) % 4
    binary_data.extend(b"\x00" * binary_padding)

    # GLB header
    header = struct.pack(
        "<III", 0x46546C67, 2, 12 + 8 + len(json_data) + 8 + len(binary_data)
    )

    # JSON chunk
    json_chunk = struct.pack("<II", len(json_data), 0x4E4F534A) + json_data

    # Binary chunk
    binary_chunk = struct.pack("<II", len(binary_data), 0x004E4942) + binary_data

    # Write GLB file
    with open(output_path, "wb") as f:
        f.write(header + json_chunk + binary_chunk)


def main():
    if len(sys.argv) != 3:
        print("Usage: python oes_to_gltf.py <input_zone.zip> <output.glb>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_filename = sys.argv[2]

    # Create output directory if it doesn't exist
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Put output file in the output directory
    output_path = os.path.join(output_dir, output_filename)

    if not os.path.exists(input_path):
        print(f"Error: Input file {input_path} not found")
        sys.exit(1)

    try:
        print(f"Reading zone file: {input_path}")
        zone_data = read_zone_file(input_path)

        print(f"Converting to glTF format...")
        create_gltf_from_zone(zone_data, output_path)

        print(f"Successfully converted to: {output_path}")

    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
