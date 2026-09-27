const path = require("path");

module.exports = {
    flowFile: "flows.json",
    userDir: process.env.NODE_RED_USER_DIR || path.join(__dirname, "data"),
    uiPort: process.env.PORT || 1880,
    credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET || "dc-twin-local",
    flowFilePretty: true,
    editorTheme: { projects: { enabled: false } },
    functionExternalModules: false,
    functionGlobalContext: {},
    logging: {
        console: { level: "info", metrics: false, audit: false }
    }
};
