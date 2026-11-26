"""Remove the profile's aspect-ratio limits from the original binary Android XML."""
import struct

ANDROID_NS = "http://schemas.android.com/apk/res/android"


def remove_attribute(chunk, start, step, count, index):
    """Remove one attribute and adjust the optional 1-based id/class/style indices."""
    pos = 16 + start + step * index
    edited = bytearray(chunk[:pos] + chunk[pos + step:])
    struct.pack_into("<I", edited, 4, len(edited))
    struct.pack_into("<H", edited, 28, count - 1)
    for offset in (30, 32, 34):
        special, = struct.unpack_from("<H", edited, offset)
        if special == index + 1:
            raise ValueError("Aspect ratio unexpectedly occupies a special attribute slot")
        if special > index + 1:
            struct.pack_into("<H", edited, offset, special - 1)
    return edited


def remove_aspect_limit(data, profile):
    chunks = []
    offset = 8
    while offset < len(data):
        kind, header_size, size = struct.unpack_from("<HHI", data, offset)
        if not 8 <= header_size <= size <= len(data) - offset:
            raise ValueError("Invalid binary XML chunk")
        chunks.append((kind, data[offset:offset + size]))
        offset += size

    pool = chunks[0][1]
    count, _, flags, base, _ = struct.unpack_from("<5I", pool, 8)
    if chunks[0][0] != 1 or flags != 0:
        raise ValueError("Expected a UTF-16 string pool")
    strings = []
    for i in range(count):
        start = base + struct.unpack_from("<I", pool, 28 + 4 * i)[0]
        length = struct.unpack_from("<H", pool, start)[0]
        strings.append(pool[start + 2:start + 2 + 2 * length].decode("utf-16le"))

    result = []
    path = []
    removed = 0
    removed_attributes = 0
    float_bits, = struct.unpack("<I", struct.pack("<f", profile.aspect_ratio))
    expected_value = (4, float_bits)
    for kind, chunk in chunks:
        if kind == 0x102:  # Start element
            name = strings[struct.unpack_from("<I", chunk, 20)[0]]
            start, step, count = struct.unpack_from("<3H", chunk, 24)
            attrs = {}
            aspect_index = None
            for i in range(count):
                pos = 16 + start + i * step
                namespace, key_index = struct.unpack_from("<II", chunk, pos)
                if namespace == 0xFFFFFFFF or strings[namespace] != ANDROID_NS:
                    continue
                key = strings[key_index]
                if key == "maxAspectRatio":
                    aspect_index = i
                datatype = chunk[pos + 15]
                value = struct.unpack_from("<I", chunk, pos + 16)[0]
                attrs[key] = strings[value] if datatype == 3 else (datatype, value)
            if name == "activity" and attrs.get("name") == profile.activity and aspect_index is not None:
                if not profile.activity_aspect_attribute or attrs["maxAspectRatio"] != expected_value:
                    raise ValueError("Unexpected launcher maxAspectRatio attribute")
                chunk = remove_attribute(chunk, start, step, count, aspect_index)
                removed_attributes += 1
            omit = (name == "meta-data" and attrs.get("name") == "android.max_aspect"
                    and path and path[-1][0] == profile.aspect_parent
                    and (profile.aspect_parent == "application" or path[-1][1] == profile.activity))
            if omit:
                if attrs.get("value") != expected_value:
                    raise ValueError("Unexpected android.max_aspect value")
                removed += 1
            path.append((name, attrs.get("name"), omit))
            if omit:
                continue
        elif kind == 0x103:  # End element
            name, _, omit = path.pop()
            if name != strings[struct.unpack_from("<I", chunk, 20)[0]]:
                raise ValueError("Unbalanced XML element")
            if omit:
                continue
        result.append(chunk)
    if removed != 1 or removed_attributes != int(profile.activity_aspect_attribute) or path:
        raise ValueError("Manifest aspect-ratio limits do not match the selected profile")
    body = b"".join(result)
    return data[:4] + struct.pack("<I", len(body) + 8) + body
