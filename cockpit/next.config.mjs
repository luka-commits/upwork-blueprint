// The cockpit runs on the member's own computer only. No compression, so the
// live run stream reaches the page line by line instead of in one late lump.
const config = {
  compress: false,
  poweredByHeader: false,
  devIndicators: false,
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
};

export default config;
