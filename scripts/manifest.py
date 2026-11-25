"""Remove the single aspect-ratio metadata element in the supported binary Android XML."""
import struct

ACTIVITY = "com.playstation.knowledge.UnityPlayerActivityWithPS4Discovery"


def remove_aspect_limit(data):
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
    for kind, chunk in chunks:
        if kind == 0x102:  # Start element
            name = strings[struct.unpack_from("<I", chunk, 20)[0]]
            start, step, count = struct.unpack_from("<3H", chunk, 24)
            attrs = {}
            for i in range(count):
                pos = 16 + start + i * step
                key = strings[struct.unpack_from("<I", chunk, pos + 4)[0]]
                datatype = chunk[pos + 15]
                value = struct.unpack_from("<I", chunk, pos + 16)[0]
                attrs[key] = strings[value] if datatype == 3 else (datatype, value)
            omit = (name == "meta-data" and attrs.get("name") == "android.max_aspect"
                    and path and path[-1][:2] == ("activity", ACTIVITY))
            if omit:
                if attrs.get("value") != (4, 0x40066666):  # Float 2.1
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
    if removed != 1 or path:
        raise ValueError("Expected exactly one aspect-ratio limit")
    body = b"".join(result)
    return data[:4] + struct.pack("<I", len(body) + 8) + body
