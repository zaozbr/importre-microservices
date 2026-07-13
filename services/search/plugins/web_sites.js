// Patterns reutilizados por multiplos sites
const ROMS_LINK_PATTERN = '<a[^>]+href="(/roms/[^"]+)"[^>]*>([^<]+)</a>';
const ANY_LINK_PATTERN = '<a[^>]+href="(/[^"]+)"[^>]*>([^<]+)</a>';

module.exports = {
  romspedia: {
    base: 'https://www.romspedia.com',
    search: 'https://www.romspedia.com/?s={query}',
    patterns: [ROMS_LINK_PATTERN]
  },
  romsgames: {
    base: 'https://www.romsgames.com',
    search: 'https://www.romsgames.com/?s={query}',
    patterns: [ROMS_LINK_PATTERN]
  },
  retromania: {
    base: 'https://www.retromania.com',
    search: 'https://www.retromania.com/?s={query}',
    patterns: [ROMS_LINK_PATTERN]
  },
  consoleroms: {
    base: 'https://www.consoleroms.com',
    search: 'https://www.consoleroms.com/?s={query}',
    patterns: [ROMS_LINK_PATTERN]
  },
  romulation: {
    base: 'https://www.romulation.org',
    search: 'https://www.romulation.org/roms/PSX?q={query}',
    patterns: [ROMS_LINK_PATTERN]
  },
  romsretro: {
    base: 'https://romsretro.com',
    search: 'https://romsretro.com/?s={query}',
    patterns: ['<a[^>]+href="(/[^"]+-rom-[^"]+)"[^>]*>([^<]+)</a>']
  },
  blueroms: {
    base: 'https://www.blueroms.ws',
    search: 'https://www.blueroms.ws/?s={query}',
    patterns: [ANY_LINK_PATTERN]
  },
  freeroms: {
    base: 'https://www.freeroms.com',
    search: 'https://www.freeroms.com/search?q={query}',
    patterns: ['<a[^>]+href="(/[^"]+\\.html)"[^>]*>([^<]+)</a>']
  },
  romspure: {
    base: 'https://romspure.cc',
    search: 'https://romspure.cc/?s={query}',
    patterns: [ROMS_LINK_PATTERN]
  },
  roms2000: {
    base: 'https://www.roms2000.com',
    search: 'https://www.roms2000.com/?s={query}',
    patterns: [ANY_LINK_PATTERN]
  },
  classicgames: {
    base: 'https://www.classicgames.com',
    search: 'https://www.classicgames.com/?s={query}',
    patterns: [ANY_LINK_PATTERN]
  },
  retrogames_games: {
    base: 'https://retrogames.games',
    search: 'https://retrogames.games/?s={query}',
    patterns: [ANY_LINK_PATTERN]
  },
  retrogames_cc: {
    base: 'https://retrogames.cc',
    search: 'https://retrogames.cc/?s={query}',
    patterns: [ANY_LINK_PATTERN]
  },
  playretrogames: {
    base: 'https://www.playretrogames.com',
    search: 'https://www.playretrogames.com/?s={query}',
    patterns: [ANY_LINK_PATTERN]
  },
  oldiesnest: {
    base: 'https://www.oldiesnest.com',
    search: 'https://www.oldiesnest.com/?s={query}',
    patterns: [ANY_LINK_PATTERN]
  }
};
