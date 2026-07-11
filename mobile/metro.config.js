const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// Enable platform-specific file resolution (.web.ts/.web.tsx before .ts/.tsx)
config.resolver.platforms = ["web", "ios", "android", "native"];

// Exclude @supabase from web bundle — uses Node.js APIs not available in browser
config.resolver.resolverMainFields = ["react-native", "browser", "main"];

module.exports = config;
