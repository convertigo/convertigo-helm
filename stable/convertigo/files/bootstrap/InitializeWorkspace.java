import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.util.*;
import com.twinsoft.convertigo.engine.util.Crypto2;

/** Apply installation configuration from mounted files before the engine starts. */
class InitializeWorkspace {
    static Path workspace, configuration, credentials, statePath;
    static Properties engine, state;
    static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null ? fallback : value;
    }
    static Properties load(Path path) throws IOException {
        Properties p = new Properties();
        if (Files.exists(path)) try (InputStream in = Files.newInputStream(path)) { p.load(in); }
        return p;
    }
    static void store(Path path, Properties p) throws IOException {
        Files.createDirectories(path.getParent());
        Path tmp = Files.createTempFile(path.getParent(), ".bootstrap-", ".tmp");
        try {
            Files.setPosixFilePermissions(tmp, PosixFilePermissions.fromString("rw-------"));
            try (OutputStream out = Files.newOutputStream(tmp)) { p.store(out, "Installation configuration"); }
            Files.move(tmp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally { Files.deleteIfExists(tmp); }
    }
    static String credential(String key) throws IOException {
        String value = Files.readString(credentials.resolve(key), StandardCharsets.UTF_8);
        if (value.isEmpty()) throw new IOException("Required installation credential is empty");
        return value;
    }
    static String fingerprint(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(digest);
    }
    static boolean hasEntries(Path directory) throws IOException {
        if (!Files.isDirectory(directory)) return false;
        try (var files = Files.list(directory)) { return files.findAny().isPresent(); }
    }
    static void setCredential(String property, String file) throws IOException {
        String value = credential(file);
        String prior = engine.getProperty(property);
        if (state.getProperty("mode").equals("existing") && prior != null && !prior.equals(value))
            throw new IOException("Existing configuration and supplied credentials differ");
        engine.setProperty(property, value);
    }
    static void prepare() throws Exception {
        if (state.isEmpty()) {
            boolean existing = hasEntries(configuration) || hasEntries(workspace.resolve("projects"))
                || Files.exists(workspace.resolve(".chart-install-complete"));
            if (existing && !env("BOOTSTRAP_ADOPT_EXISTING", "false").equals("true"))
                throw new IOException("Existing workspace requires explicit credential adoption");
            if (!existing && !env("BOOTSTRAP_CRYPTO_COMPATIBLE", "false").equals("true"))
                throw new IOException("Engine passphrase compatibility must be confirmed before new initialization");
            state.setProperty("mode", existing ? "existing" : "new");
            if (!existing) state.setProperty("fingerprint", fingerprint(credential("crypto-passphrase")));
            for (String key : List.of("baserow-admin-password", "billing-password", "postgres-password", "couchdb-password"))
                state.setProperty("credential." + key, fingerprint(credential(key)));
            if (env("BOOTSTRAP_REDIS_PASSWORD", "false").equals("true"))
                state.setProperty("credential.redis-password", fingerprint(credential("redis-password")));
            // Persist the identity before subsequent writes, so interrupted setup can resume safely.
            store(statePath, state);
        }
        for (String key : state.stringPropertyNames()) {
            if (key.startsWith("credential.") && !state.getProperty(key).equals(fingerprint(credential(key.substring(11)))))
                throw new IOException("Installation credential identity changed");
        }
        if (state.getProperty("mode").equals("new")) {
            String phrase = credential("crypto-passphrase");
            if (phrase.length() < 32 || !fingerprint(phrase).equals(state.getProperty("fingerprint")))
                throw new IOException("Installation passphrase identity changed");
            String prior = engine.getProperty("crypto.passphrase");
            if (prior != null && !prior.equals(phrase))
                throw new IOException("Existing passphrase differs from installation identity");
            engine.setProperty("crypto.passphrase", phrase);
            engine.putIfAbsent("log4j.logger.cems.Context", "WARN");
        } else if (!state.getProperty("mode").equals("existing")) {
            throw new IOException("Unknown installation identity");
        }
        // The existing mode never sets, removes or changes crypto.passphrase.
        setCredential("fullsync.couch.password", "couchdb-password");
        if (Files.exists(credentials.resolve("couchdb-username")))
            setCredential("fullsync.couch.username", "couchdb-username");
        else {
            String username = env("BOOTSTRAP_COUCH_USER", "admin");
            String prior = engine.getProperty("fullsync.couch.username");
            if (state.getProperty("mode").equals("existing") && prior != null && !prior.equals(username))
                throw new IOException("Existing CouchDB account differs from supplied configuration");
            engine.setProperty("fullsync.couch.username", username);
        }
        setCredential("billing.persistence.jdbc.password", "postgres-password");
        if (env("BOOTSTRAP_REDIS_PASSWORD", "false").equals("true"))
            setCredential("session.redis.password", "redis-password");
        store(configuration.resolve("engine.properties"), engine);
    }
    static void symbols() throws Exception {
        if (!state.getProperty("mode", "").equals("new")) return;
        String phrase = engine.getProperty("crypto.passphrase");
        if (phrase == null || !fingerprint(phrase).equals(state.getProperty("fingerprint")))
            throw new IOException("Installation passphrase identity is unavailable");
        Path path = configuration.resolve("global_symbols.properties");
        Properties symbols = load(path);
        String adminPassword = credential("baserow-admin-password");
        String billingPassword = credential("billing-password");
        if (!fingerprint(adminPassword).equals(state.getProperty("credential.baserow-admin-password"))
            || !fingerprint(billingPassword).equals(state.getProperty("credential.billing-password")))
            throw new IOException("Installation credential identity changed during initialization");
        String admin = Crypto2.encodeToHexString(phrase, adminPassword);
        String billing = Crypto2.encodeToHexString(phrase, billingPassword);
        if (admin == null || billing == null) throw new IOException("Symbol initialization failed");
        symbols.setProperty("lib_baserow.adminuser", env("BOOTSTRAP_BASEROW_EMAIL", "admin@convertigo.com"));
        symbols.setProperty("lib_baserow.password.secret", admin);
        symbols.setProperty("C8OBilling.password.secret", billing);
        store(path, symbols);
    }
    public static void main(String[] args) {
        try {
            workspace = Path.of(env("WORKSPACE", "/workspace"));
            configuration = workspace.resolve("configuration");
            credentials = Path.of(env("INSTALLATION_CREDENTIALS_DIR", "/run/convertigo-installation"));
            statePath = configuration.resolve(".chart-crypto-state");
            engine = load(configuration.resolve("engine.properties"));
            state = load(statePath);
            if (args.length != 1) throw new IOException("Missing initialization action");
            if (args[0].equals("prepare")) prepare();
            else if (args[0].equals("symbols")) symbols();
            else throw new IOException("Unknown initialization action");
        } catch (Throwable failure) {
            // Do not include input data or exception messages in container logs.
            System.err.println("Workspace credential initialization failed; review installation state privately");
            System.exit(1);
        }
    }
}
