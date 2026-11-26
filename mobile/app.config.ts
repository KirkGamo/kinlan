import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * app.json holds the configuration; this only fills in what differs on EAS Build.
 * google-services.json (Firebase, for push) is git-ignored, so EAS never receives it with the
 * project files: it comes from the secret file variable GOOGLE_SERVICES_JSON on the preview and
 * production environments instead (issue #92). Local builds keep using the file in this folder.
 */
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...(config as ExpoConfig),
  android: {
    ...config.android,
    googleServicesFile: process.env.GOOGLE_SERVICES_JSON ?? config.android?.googleServicesFile,
  },
});
