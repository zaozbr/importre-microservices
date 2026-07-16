#!/usr/bin/env node
// Decoder ECM (Error Code Modeler) em Node.js
// Le input com readFileSync, escreve output via stream (evita OOM no output)
// Baseado no unecm.c de Neill Corlett
// Uso: node unecm.js arquivo.ecm [saida]
// Export: decodeEcmStream(inputPath, outputPath) => Promise<number>

const fs = require('fs');
const path = require('path');

// LUTs para ECC/EDC
const eccF = new Uint8Array(256);
const eccB = new Uint8Array(256);
const edcLut = new Uint32Array(256);

function eccedcInit() {
  for (let i = 0; i < 256; i++) {
    let j = (i << 1) ^ (i & 0x80 ? 0x11D : 0);
    j &= 0xFF;
    eccF[i] = j;
    eccB[i ^ j] = i;
    let edc = i;
    for (let k = 0; k < 8; k++) edc = (edc >>> 1) ^ (edc & 1 ? 0xD8018001 : 0);
    edcLut[i] = edc >>> 0;
  }
}

function edcPartial(edc, src, size) {
  for (let i = 0; i < size; i++) edc = (edc >>> 8) ^ edcLut[(edc ^ src[i]) & 0xFF];
  return edc >>> 0;
}

function edcCompute(src, size) {
  const edc = edcPartial(0, src, size);
  return [edc & 0xFF, (edc >>> 8) & 0xFF, (edc >>> 16) & 0xFF, (edc >>> 24) & 0xFF];
}

function eccComputeBlock(src, majorCount, minorCount, majorMult, minorInc, dest) {
  const size = majorCount * minorCount;
  for (let major = 0; major < majorCount; major++) {
    let index = (major >> 1) * majorMult + (major & 1);
    let eccA = 0, eccB = 0;
    for (let minor = 0; minor < minorCount; minor++) {
      const temp = src[index];
      index += minorInc;
      if (index >= size) index -= size;
      eccA ^= temp;
      eccB ^= temp;
      eccA = eccF[eccA];
    }
    eccA = eccB[eccF[eccA] ^ eccB];
    dest[major] = eccA;
    dest[major + majorCount] = eccA ^ eccB;
  }
}

function eccGenerate(sector, zeroaddress) {
  const address = [0, 0, 0, 0];
  if (zeroaddress) {
    for (let i = 0; i < 4; i++) {
      address[i] = sector[12 + i];
      sector[12 + i] = 0;
    }
  }
  eccComputeBlock(sector.subarray(0xC), 86, 24, 2, 86, sector.subarray(0x81C));
  eccComputeBlock(sector.subarray(0xC), 52, 43, 86, 88, sector.subarray(0x8C8));
  if (zeroaddress) {
    for (let i = 0; i < 4; i++) sector[12 + i] = address[i];
  }
}

function eccedcGenerate(sector, type) {
  switch (type) {
    case 1: {
      const edc = edcCompute(sector.subarray(0x00, 0x810));
      for (let i = 0; i < edc.length; i++) sector[0x810 + i] = edc[i];
      for (let i = 0; i < 8; i++) sector[0x814 + i] = 0;
      eccGenerate(sector, 0);
      break;
    }
    case 2: {
      const edc2 = edcCompute(sector.subarray(0x10, 0x818));
      for (let i = 0; i < edc2.length; i++) sector[0x818 + i] = edc2[i];
      eccGenerate(sector, 1);
      break;
    }
    case 3: {
      const edc3 = edcCompute(sector.subarray(0x10, 0x92C));
      for (let i = 0; i < edc3.length; i++) sector[0x92C + i] = edc3[i];
      break;
    }
  }
}

// Decoder: le input de uma vez, escreve output via stream
async function decodeEcmStream(inputPath, outputPath) {
  const input = fs.readFileSync(inputPath);

  // Header: 4 bytes "ECM\0"
  if (input.length < 4 || input[0] !== 0x45 || input[1] !== 0x43 || input[2] !== 0x4D || input[3] !== 0x00) {
    throw new Error('Header ECM nao encontrado');
  }

  const writeStream = fs.createWriteStream(outputPath, { highWaterMark: 4 * 1024 * 1024 });
  let checkedc = 0;
  let outBytes = 0;
  let pos = 4;

  // Buffer acumulado para escrita (flush periodicamente)
  const writeBuf = [];
  const FLUSH_THRESHOLD = 4 * 1024 * 1024; // 4MB

  async function flush() {
    if (writeBuf.length === 0) return;
    const data = Buffer.concat(writeBuf);
    writeBuf.length = 0;
    return new Promise((resolve) => {
      const ok = writeStream.write(data);
      if (ok) resolve();
      else writeStream.once('drain', () => resolve());
    });
  }

  while (pos < input.length) {
    // Ler varint: tipo + num
    const recordStart = pos;
    let c = input[pos++];
    let bits = 5;
    const type = c & 3;
    let num = (c >>> 2) & 0x1F;

    while (c & 0x80) {
      if (pos >= input.length) throw new Error(`EOF inesperado no varint (pos=${recordStart})`);
      c = input[pos++];
      if (bits < 32) {
        num = (num | ((c & 0x7F) << bits)) >>> 0;
      }
      bits += 7;
      if (bits > 35) throw new Error(`Varint overflow (pos=${recordStart})`);
    }

    if (num === 0xFFFFFFFF) break; // marcador de fim
    num = (num + 1) >>> 0;
    if (num === 0 || num >= 0x80000000) throw new Error(`num invalido: ${num} (pos=${recordStart})`);

    if (type === 0) {
      // Raw: copiar num bytes diretamente
      if (pos + num > input.length) throw new Error(`Dados insuficientes para type=0 num=${num} (pos=${pos})`);
      const chunk = Buffer.from(input.subarray(pos, pos + num));
      checkedc = edcPartial(checkedc, chunk, num);
      writeBuf.push(chunk);
      outBytes += num;
      pos += num;
    } else {
      // Tipos 1, 2, 3: setores CD-ROM
      for (let s = 0; s < num; s++) {
        const sector = new Uint8Array(2352);
        sector[0] = 0x00;
        for (let i = 1; i <= 10; i++) sector[i] = 0xFF;
        sector[11] = 0x00;

        let writeSize, writeOffset;
        switch (type) {
          case 1:
            sector[0x0F] = 0x01;
            if (pos + 3 + 0x800 > input.length) throw new Error(`Dados insuficientes type=1 (pos=${pos})`);
            sector.set(input.subarray(pos, pos + 3), 0x0C); pos += 3;
            sector.set(input.subarray(pos, pos + 0x800), 0x10); pos += 0x800;
            eccedcGenerate(sector, 1);
            checkedc = edcPartial(checkedc, sector, 2352);
            writeSize = 2352;
            writeOffset = 0;
            break;
          case 2:
            sector[0x0F] = 0x02;
            if (pos + 0x804 > input.length) throw new Error(`Dados insuficientes type=2 (pos=${pos})`);
            sector.set(input.subarray(pos, pos + 0x804), 0x14); pos += 0x804;
            sector[0x10] = sector[0x14]; sector[0x11] = sector[0x15];
            sector[0x12] = sector[0x16]; sector[0x13] = sector[0x17];
            eccedcGenerate(sector, 2);
            checkedc = edcPartial(checkedc, sector.subarray(0x10), 2336);
            writeSize = 2336;
            writeOffset = 0x10;
            break;
          case 3:
            sector[0x0F] = 0x02;
            if (pos + 0x918 > input.length) throw new Error(`Dados insuficientes type=3 (pos=${pos})`);
            sector.set(input.subarray(pos, pos + 0x918), 0x14); pos += 0x918;
            sector[0x10] = sector[0x14]; sector[0x11] = sector[0x15];
            sector[0x12] = sector[0x16]; sector[0x13] = sector[0x17];
            eccedcGenerate(sector, 3);
            checkedc = edcPartial(checkedc, sector.subarray(0x10), 2336);
            writeSize = 2336;
            writeOffset = 0x10;
            break;
          default:
            throw new Error(`Tipo desconhecido: ${type} (pos=${recordStart})`);
        }
        writeBuf.push(Buffer.from(sector.subarray(writeOffset, writeOffset + writeSize)));
        outBytes += writeSize;
      }
    }

    // Flush periodico
    if (outBytes >= FLUSH_THRESHOLD || writeBuf.length > 1000) {
      let totalSize = 0;
      for (const b of writeBuf) totalSize += b.length;
      if (totalSize >= FLUSH_THRESHOLD) {
        await flush();
      }
    }
  }

  // Flush final
  await flush();

  // Verificar EDC (4 bytes apos o marcador 0xFFFFFFFF)
  if (pos + 4 <= input.length) {
    const fileEdc = input.readUInt32LE(pos);
    if (fileEdc !== checkedc) {
      console.error(`Aviso: EDC mismatch (file: 0x${fileEdc.toString(16)}, calc: 0x${checkedc.toString(16)})`);
    }
  }

  return new Promise((resolve) => {
    writeStream.end(() => resolve(outBytes));
  });
}

module.exports = { decodeEcmStream, eccedcInit };

// Main (CLI)
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Uso: node unecm.js <arquivo.ecm> [saida]');
    process.exit(1);
  }

  eccedcInit();

  const inputPath = args[0];
  const outputPath = args[1] || inputPath.replace(/\.ecm$/i, '');

  if (!fs.existsSync(inputPath)) {
    console.error(`Arquivo nao encontrado: ${inputPath}`);
    process.exit(1);
  }

  const inSize = fs.statSync(inputPath).size;
  process.stderr.write(`Decodificando: ${path.basename(inputPath)} (${(inSize / 1048576).toFixed(1)}MB)... `);

  decodeEcmStream(inputPath, outputPath)
    .then((outSize) => {
      console.log(`OK (${(outSize / 1048576).toFixed(1)}MB)`);
      fs.unlinkSync(inputPath);
      console.log(`Original .ecm deletado`);
    })
    .catch((e) => {
      console.error(`ERRO: ${e.message}`);
      try { if (fs.existsSync(outputPath)) fs.unlinkSync(outputPath); } catch {}
      process.exit(1);
    });
}
