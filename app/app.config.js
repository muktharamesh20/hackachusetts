/**
 * Extends app.json with config that depends on .env values.
 *
 * Google Sign-In on iOS needs the reversed iOS OAuth client ID registered as a
 * URL scheme. The client ID lives in .env (EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID),
 * so the plugin is added here rather than hardcoded in app.json.
 */
module.exports = ({ config }) => {
  const iosClientId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID?.trim();
  if (!iosClientId) return config;

  const iosUrlScheme =
    "com.googleusercontent.apps." +
    iosClientId.replace(/\.apps\.googleusercontent\.com$/, "");

  return {
    ...config,
    plugins: [
      ...(config.plugins ?? []),
      ["@react-native-google-signin/google-signin", { iosUrlScheme }],
    ],
  };
};
