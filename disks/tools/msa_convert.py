import sys, struct

def msa_to_st(data):
    assert data[0:2] == b'\x0e\x0f', "not an MSA file"
    sectors_per_track = struct.unpack('>H', data[2:4])[0]
    sides_minus1 = struct.unpack('>H', data[4:6])[0]
    start_track = struct.unpack('>H', data[6:8])[0]
    end_track = struct.unpack('>H', data[8:10])[0]
    num_sides = sides_minus1 + 1
    track_size = sectors_per_track * 512
    pos = 10
    out = bytearray()
    for track in range(start_track, end_track + 1):
        for side in range(num_sides):
            data_len = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2
            chunk = data[pos:pos+data_len]
            pos += data_len
            if data_len == track_size:
                out += chunk
            else:
                i = 0
                res = bytearray()
                while i < len(chunk):
                    b = chunk[i]
                    if b == 0xE5:
                        rb = chunk[i+1]
                        cnt = struct.unpack('>H', chunk[i+2:i+4])[0]
                        res += bytes([rb]) * cnt
                        i += 4
                    else:
                        res.append(b)
                        i += 1
                assert len(res) == track_size, f"track {track} side {side}: {len(res)} != {track_size}"
                out += res
    return bytes(out), sectors_per_track, num_sides, start_track, end_track

if __name__ == '__main__':
    infile, outfile = sys.argv[1], sys.argv[2]
    with open(infile, 'rb') as f:
        data = f.read()
    st, spt, sides, st_trk, end_trk = msa_to_st(data)
    with open(outfile, 'wb') as f:
        f.write(st)
    print(f"sectors/track={spt} sides={sides} tracks={st_trk}-{end_trk} total_bytes={len(st)}")
