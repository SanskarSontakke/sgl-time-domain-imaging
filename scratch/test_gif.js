// Pure JS GIF89a encoder with LZW compression
const fs = require('fs');

class SimpleGifEncoder {
  constructor(width, height, delay = 10) {
    this.width = width;
    this.height = height;
    this.delay = delay; // in 10ms units (e.g. 10 = 100ms)
    this.frames = [];
    this.palette = [];
  }

  setPalette(palette) {
    this.palette = palette; // array of [r,g,b] up to 256 colors
    while (this.palette.length < 256) {
      this.palette.push([0, 0, 0]);
    }
  }

  addFrame(indexedPixels) {
    this.frames.push(indexedPixels);
  }

  encode() {
    const buffers = [];

    // Header: GIF89a
    buffers.push(Buffer.from('GIF89a', 'ascii'));

    // Logical Screen Descriptor
    const lsd = Buffer.alloc(7);
    lsd.writeUInt16LE(this.width, 0);
    lsd.writeUInt16LE(this.height, 2);
    lsd[4] = 0xF7; // Global color table flag = 1, color resolution = 7, sort = 0, size = 7 (256 colors)
    lsd[5] = 0; // background color index
    lsd[6] = 0; // pixel aspect ratio
    buffers.push(lsd);

    // Global Color Table (256 * 3 = 768 bytes)
    const gct = Buffer.alloc(768);
    for (let i = 0; i < 256; i++) {
      const color = this.palette[i] || [0, 0, 0];
      gct[i * 3] = color[0];
      gct[i * 3 + 1] = color[1];
      gct[i * 3 + 2] = color[2];
    }
    buffers.push(gct);

    // Netscape Application Block for Looping
    const loop = Buffer.from([
      0x21, 0xFF, 0x0B,
      0x4E, 0x45, 0x54, 0x53, 0x43, 0x41, 0x50, 0x45, 0x32, 0x2E, 0x30, // "NETSCAPE2.0"
      0x03, 0x01, 0x00, 0x00, // loop count = 0 (infinite)
      0x00
    ]);
    buffers.push(loop);

    // Add each frame
    for (const frame of this.frames) {
      // Graphic Control Extension
      const gce = Buffer.from([
        0x21, 0xF9, 0x04,
        0x04, // disposal method = do not dispose
        this.delay & 0xFF, (this.delay >> 8) & 0xFF,
        0x00, // transparent color index
        0x00
      ]);
      buffers.push(gce);

      // Image Descriptor
      const id = Buffer.alloc(10);
      id[0] = 0x2C; // image separator
      id.writeUInt16LE(0, 1); // left
      id.writeUInt16LE(0, 3); // top
      id.writeUInt16LE(this.width, 5);
      id.writeUInt16LE(this.height, 7);
      id[9] = 0x00; // no local color table
      buffers.push(id);

      // LZW compression
      buffers.push(this.lzwCompress(frame, 8));
    }

    // Trailer
    buffers.push(Buffer.from([0x3B]));

    return Buffer.concat(buffers);
  }

  lzwCompress(pixels, colorDepth) {
    const minCodeSize = Math.max(2, colorDepth);
    const clearCode = 1 << minCodeSize;
    const endCode = clearCode + 1;

    let codeSize = minCodeSize + 1;
    let maxCode = (1 << codeSize) - 1;

    const dictionary = new Map();
    function resetDict() {
      dictionary.clear();
      for (let i = 0; i < clearCode; i++) {
        dictionary.set(String.fromCharCode(i), i);
      }
    }
    resetDict();
    let nextCode = endCode + 1;

    const outBits = [];
    function writeBits(val, count) {
      for (let i = 0; i < count; i++) {
        outBits.push((val >> i) & 1);
      }
    }

    writeBits(clearCode, codeSize);

    let prefix = '';
    for (let i = 0; i < pixels.length; i++) {
      const c = String.fromCharCode(pixels[i]);
      const pc = prefix + c;
      if (dictionary.has(pc)) {
        prefix = pc;
      } else {
        writeBits(dictionary.get(prefix), codeSize);
        if (nextCode <= 4095) {
          dictionary.set(pc, nextCode++);
          if (nextCode > maxCode && codeSize < 12) {
            codeSize++;
            maxCode = (1 << codeSize) - 1;
          }
        } else {
          writeBits(clearCode, codeSize);
          resetDict();
          codeSize = minCodeSize + 1;
          maxCode = (1 << codeSize) - 1;
          nextCode = endCode + 1;
        }
        prefix = c;
      }
    }
    if (prefix.length > 0) {
      writeBits(dictionary.get(prefix), codeSize);
    }
    writeBits(endCode, codeSize);

    // Convert bits to byte stream with sub-blocks
    const bytes = [];
    bytes.push(minCodeSize);

    const dataBytes = [];
    let curByte = 0;
    let bitIdx = 0;
    for (const bit of outBits) {
      curByte |= bit << bitIdx;
      bitIdx++;
      if (bitIdx === 8) {
        dataBytes.push(curByte);
        curByte = 0;
        bitIdx = 0;
      }
    }
    if (bitIdx > 0) {
      dataBytes.push(curByte);
    }

    // Split into chunks of max 254 bytes
    for (let i = 0; i < dataBytes.length; i += 254) {
      const chunk = dataBytes.slice(i, i + 254);
      bytes.push(chunk.length);
      for (const b of chunk) bytes.push(b);
    }
    bytes.push(0x00); // block terminator

    return Buffer.from(bytes);
  }
}

module.exports = SimpleGifEncoder;

// Quick test
if (require.main === module) {
  const enc = new SimpleGifEncoder(64, 64, 10);
  const pal = [];
  for (let i = 0; i < 256; i++) {
    pal.push([i, 255 - i, (i * 2) % 256]);
  }
  enc.setPalette(pal);

  for (let f = 0; f < 10; f++) {
    const frame = new Uint8Array(64 * 64);
    for (let y = 0; y < 64; y++) {
      for (let x = 0; x < 64; x++) {
        frame[y * 64 + x] = (x + y + f * 10) % 256;
      }
    }
    enc.addFrame(frame);
  }

  const gifBuf = enc.encode();
  fs.writeFileSync('scratch/test.gif', gifBuf);
  console.log('GIF generated successfully, size:', gifBuf.length, 'bytes');
}
