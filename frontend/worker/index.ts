interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  first<T = Record<string, unknown>>(): Promise<T | null>;
  all<T = Record<string, unknown>>(): Promise<{ results: T[] }>;
  run(): Promise<unknown>;
}

interface D1Database {
  prepare(query: string): D1PreparedStatement;
  batch(statements: D1PreparedStatement[]): Promise<unknown[]>;
}

interface R2ObjectBody {
  body: ReadableStream;
  httpEtag: string;
  writeHttpMetadata(headers: Headers): void;
}

interface R2Bucket {
  get(key: string): Promise<R2ObjectBody | null>;
  put(
    key: string,
    value: ArrayBuffer,
    options?: { httpMetadata?: { contentType?: string } },
  ): Promise<unknown>;
}

interface Env {
  DB: D1Database;
  MEDIA: R2Bucket;
}

type UserRow = {
  id: string;
  email: string;
  password_hash: string;
  display_name: string;
  bio: string | null;
  avatar_url: string | null;
  role: "owner" | "veterinarian";
  clinic_name: string | null;
  license_number: string | null;
  created_at: string;
};

type AnimalRow = {
  id: string;
  name: string;
  species: string;
  breed: string | null;
  birth_date: string | null;
  photo_url: string | null;
  photo_position_x: number;
  photo_position_y: number;
  photo_zoom: number;
  age_category: "baby" | "young" | "adult" | "senior" | "unknown";
  owner_id: string;
  created_at: string;
};

class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const OWNER_ID = "11111111-1111-4111-8111-111111111111";
const VET_ID = "22222222-2222-4222-8222-222222222222";
const BUDDY_ID = "33333333-3333-4333-8333-333333333333";
const FOOD_POST_ID = "44444444-4444-4444-8444-444444444444";
const CHECKUP_POST_ID = "55555555-5555-4555-8555-555555555555";

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL, bio TEXT, avatar_url TEXT, role TEXT NOT NULL,
    clinic_name TEXT, license_number TEXT, created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS animals (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, species TEXT NOT NULL, breed TEXT,
    birth_date TEXT, photo_url TEXT, photo_position_x INTEGER NOT NULL DEFAULT 50,
    photo_position_y INTEGER NOT NULL DEFAULT 50, photo_zoom REAL NOT NULL DEFAULT 1,
    age_category TEXT NOT NULL DEFAULT 'unknown', owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
    author_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY, post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL, created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS ai_analysis_logs (
    id TEXT PRIMARY KEY, animal_id TEXT REFERENCES animals(id) ON DELETE SET NULL,
    image_key TEXT NOT NULL, image_url TEXT NOT NULL, model_version TEXT NOT NULL,
    species TEXT NOT NULL, species_confidence REAL NOT NULL, result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
  )`,
  "CREATE UNIQUE INDEX IF NOT EXISTS users_email_idx ON users(email)",
  "CREATE INDEX IF NOT EXISTS users_role_idx ON users(role)",
  "CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id)",
  "CREATE INDEX IF NOT EXISTS animals_owner_idx ON animals(owner_id)",
  "CREATE INDEX IF NOT EXISTS posts_created_idx ON posts(created_at)",
  "CREATE INDEX IF NOT EXISTS comments_post_idx ON comments(post_id)",
  "CREATE INDEX IF NOT EXISTS analysis_created_idx ON ai_analysis_logs(created_at)",
];

let readyPromise: Promise<void> | null = null;

function nowIso(): string {
  return new Date().toISOString();
}

function json(value: unknown, status = 200): Response {
  return Response.json(value, { status });
}

function noContent(): Response {
  return new Response(null, { status: 204 });
}

function publicUser(row: UserRow) {
  return {
    id: row.id,
    email: row.email,
    display_name: row.display_name,
    role: row.role,
    bio: row.bio,
    avatar_url: row.avatar_url,
    clinic_name: row.clinic_name,
    license_number: row.license_number,
    created_at: row.created_at,
  };
}

function publicAnimal(row: AnimalRow) {
  return { ...row };
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(hex: string): Uint8Array {
  if (!/^[0-9a-f]+$/i.test(hex) || hex.length % 2 !== 0) return new Uint8Array();
  return new Uint8Array(hex.match(/.{2}/g)?.map((value) => Number.parseInt(value, 16)) ?? []);
}

async function derivePassword(password: string, salt: Uint8Array, iterations: number): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    key,
    256,
  );
  return new Uint8Array(bits);
}

async function hashPassword(password: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const digest = await derivePassword(password, salt, 100_000);
  return `pbkdf2$100000$${bytesToHex(salt)}$${bytesToHex(digest)}`;
}

async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const [scheme, count, saltHex, digestHex] = stored.split("$");
  if (scheme !== "pbkdf2" || !count || !saltHex || !digestHex) return false;
  const expected = hexToBytes(digestHex);
  const actual = await derivePassword(password, hexToBytes(saltHex), Number.parseInt(count, 10));
  if (expected.length !== actual.length) return false;
  let mismatch = 0;
  for (let index = 0; index < expected.length; index += 1) mismatch |= expected[index] ^ actual[index];
  return mismatch === 0;
}

async function initializeDatabase(env: Env): Promise<void> {
  await env.DB.batch(SCHEMA.map((statement) => env.DB.prepare(statement)));
  const existing = await env.DB.prepare("SELECT id FROM users LIMIT 1").first<{ id: string }>();
  if (existing) return;

  const [ownerPassword, vetPassword] = await Promise.all([
    hashPassword("demo1234"),
    hashPassword("demo1234"),
  ]);
  const created = nowIso();
  await env.DB.batch([
    env.DB.prepare(
      `INSERT OR IGNORE INTO users
       (id, email, password_hash, display_name, bio, avatar_url, role, clinic_name, license_number, created_at)
       VALUES (?, ?, ?, ?, ?, NULL, 'owner', NULL, NULL, ?)`,
    ).bind(
      OWNER_ID,
      "demo.owner@uepemmy.com",
      ownerPassword,
      "Alex the Pet Owner",
      "Proud owner of Buddy the Labrador. Learning something new about dogs every day.",
      created,
    ),
    env.DB.prepare(
      `INSERT OR IGNORE INTO users
       (id, email, password_hash, display_name, bio, avatar_url, role, clinic_name, license_number, created_at)
       VALUES (?, ?, ?, ?, ?, NULL, 'veterinarian', ?, ?, ?)`,
    ).bind(
      VET_ID,
      "demo.vet@uepemmy.com",
      vetPassword,
      "Dr. Maya Fischer",
      "Small-animal veterinarian with 12 years of experience. Special interest in nutrition and preventive care.",
      "Riverside Veterinary Clinic",
      "VET-2024-0042",
      created,
    ),
    env.DB.prepare(
      `INSERT OR IGNORE INTO animals
       (id, name, species, breed, birth_date, photo_url, photo_position_x, photo_position_y, photo_zoom, age_category, owner_id, created_at)
       VALUES (?, 'Buddy', 'dog', 'Labrador Retriever', '2021-03-14', NULL, 50, 50, 1, 'adult', ?, ?)`,
    ).bind(BUDDY_ID, OWNER_ID, created),
    env.DB.prepare(
      `INSERT OR IGNORE INTO posts (id, title, content, author_id, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    ).bind(
      FOOD_POST_ID,
      "How much should an adult Labrador eat per day?",
      "Buddy is a 5-year-old Lab, around 30 kg, and he acts hungry all the time. The bag says 350 g/day but he inhales it in seconds. Is it okay to give him more, or are Labs just like this?",
      OWNER_ID,
      created,
      created,
    ),
    env.DB.prepare(
      `INSERT OR IGNORE INTO posts (id, title, content, author_id, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    ).bind(
      CHECKUP_POST_ID,
      "Reminder: senior pets benefit from twice-yearly checkups",
      "Once dogs and cats reach their senior years, annual exams can miss slow-developing issues. Twice-yearly visits with basic bloodwork often catch these much earlier.",
      VET_ID,
      created,
      created,
    ),
    env.DB.prepare(
      `INSERT OR IGNORE INTO comments (id, post_id, author_id, content, created_at)
       VALUES ('66666666-6666-4666-8666-666666666666', ?, ?, ?, ?)`,
    ).bind(
      FOOD_POST_ID,
      VET_ID,
      "Labs are famously food-motivated. Use body condition score and the feeding guide for the target weight rather than appetite alone.",
      created,
    ),
  ]);
}

function ensureDatabase(env: Env): Promise<void> {
  readyPromise ??= initializeDatabase(env).catch((error) => {
    readyPromise = null;
    throw error;
  });
  return readyPromise;
}

async function readJson<T extends object>(request: Request): Promise<T> {
  try {
    return (await request.json()) as T;
  } catch {
    throw new HttpError(400, "Invalid JSON request body.");
  }
}

async function userById(env: Env, id: string): Promise<UserRow | null> {
  return env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(id).first<UserRow>();
}

async function currentUser(request: Request, env: Env): Promise<UserRow | null> {
  const authorization = request.headers.get("authorization") ?? "";
  if (!authorization.startsWith("Bearer ")) return null;
  const token = authorization.slice(7).trim();
  if (!token) return null;
  return env.DB.prepare(
    `SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.token = ? AND s.expires_at > ?`,
  ).bind(token, Date.now()).first<UserRow>();
}

async function requireUser(request: Request, env: Env): Promise<UserRow> {
  const user = await currentUser(request, env);
  if (!user) throw new HttpError(401, "Authentication required.");
  return user;
}

async function createSession(env: Env, userId: string): Promise<string> {
  const token = `${crypto.randomUUID()}${crypto.randomUUID().replaceAll("-", "")}`;
  await env.DB.prepare("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)")
    .bind(token, userId, Date.now() + 7 * 24 * 60 * 60 * 1000)
    .run();
  return token;
}

function validateImage(file: File): void {
  if (!IMAGE_TYPES.has(file.type)) {
    throw new HttpError(415, "Unsupported image type. Allowed: image/jpeg, image/png, image/webp.");
  }
  if (file.size === 0) throw new HttpError(400, "Uploaded file is empty.");
  if (file.size > MAX_UPLOAD_BYTES) throw new HttpError(413, "Image exceeds the 10 MB upload limit.");
}

function extensionFor(file: File): string {
  const fromName = file.name.toLowerCase().match(/\.[a-z0-9]{1,5}$/)?.[0];
  if (fromName) return fromName;
  return file.type === "image/png" ? ".png" : file.type === "image/webp" ? ".webp" : ".jpg";
}

async function storeImage(env: Env, prefix: string, file: File): Promise<{ key: string; url: string; bytes: Uint8Array }> {
  validateImage(file);
  const date = new Date().toISOString().slice(0, 10).replaceAll("-", "/");
  const key = `${prefix}/${date}/${crypto.randomUUID()}${extensionFor(file)}`;
  const buffer = await file.arrayBuffer();
  await env.MEDIA.put(key, buffer, { httpMetadata: { contentType: file.type } });
  const url = `/media/${key.split("/").map(encodeURIComponent).join("/")}`;
  return { key, url, bytes: new Uint8Array(buffer) };
}

async function uploadedFile(request: Request): Promise<{ form: FormData; file: File }> {
  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File)) throw new HttpError(400, "Image file is required.");
  return { form, file };
}

async function ownedAnimal(env: Env, animalId: string, ownerId: string): Promise<AnimalRow> {
  const animal = await env.DB.prepare("SELECT * FROM animals WHERE id = ? AND owner_id = ?")
    .bind(animalId, ownerId)
    .first<AnimalRow>();
  if (!animal) throw new HttpError(404, `Pet ${animalId} not found.`);
  return animal;
}

function authorFromJoined(row: Record<string, unknown>): ReturnType<typeof publicUser> {
  return publicUser({
    id: String(row.author_user_id),
    email: String(row.author_email),
    password_hash: "",
    display_name: String(row.author_display_name),
    bio: (row.author_bio as string | null) ?? null,
    avatar_url: (row.author_avatar_url as string | null) ?? null,
    role: row.author_role as UserRow["role"],
    clinic_name: (row.author_clinic_name as string | null) ?? null,
    license_number: (row.author_license_number as string | null) ?? null,
    created_at: String(row.author_created_at),
  });
}

const POST_SELECT = `
  SELECT p.id, p.title, p.content, p.created_at,
    u.id AS author_user_id, u.email AS author_email, u.display_name AS author_display_name,
    u.bio AS author_bio, u.avatar_url AS author_avatar_url, u.role AS author_role,
    u.clinic_name AS author_clinic_name, u.license_number AS author_license_number,
    u.created_at AS author_created_at,
    (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
  FROM posts p JOIN users u ON u.id = p.author_id`;

function postFromJoined(row: Record<string, unknown>) {
  return {
    id: String(row.id),
    title: String(row.title),
    content: String(row.content),
    author: authorFromJoined(row),
    comment_count: Number(row.comment_count),
    created_at: String(row.created_at),
  };
}

async function postDetail(env: Env, postId: string) {
  const row = await env.DB.prepare(`${POST_SELECT} WHERE p.id = ?`).bind(postId).first<Record<string, unknown>>();
  if (!row) throw new HttpError(404, `Post ${postId} not found.`);
  const comments = await env.DB.prepare(
    `SELECT c.id, c.content, c.created_at,
      u.id AS author_user_id, u.email AS author_email, u.display_name AS author_display_name,
      u.bio AS author_bio, u.avatar_url AS author_avatar_url, u.role AS author_role,
      u.clinic_name AS author_clinic_name, u.license_number AS author_license_number,
      u.created_at AS author_created_at
     FROM comments c JOIN users u ON u.id = c.author_id
     WHERE c.post_id = ? ORDER BY c.created_at`,
  ).bind(postId).all<Record<string, unknown>>();
  return {
    ...postFromJoined(row),
    comments: comments.results.map((comment) => ({
      id: String(comment.id),
      content: String(comment.content),
      author: authorFromJoined(comment),
      created_at: String(comment.created_at),
    })),
  };
}

const SPECIES_PROFILES = [
  {
    species: "dog",
    breeds: [
      ["Labrador Retriever", ["short coat", "floppy ears", "athletic build"]],
      ["German Shepherd", ["erect ears", "double coat", "sloped back"]],
      ["Golden Retriever", ["long golden coat", "feathered tail", "broad head"]],
      ["French Bulldog", ["bat ears", "compact build", "short muzzle"]],
      ["Border Collie", ["medium coat", "alert expression", "agile frame"]],
    ],
    ages: [[0, 1], [1, 3], [3, 8], [8, 14]],
  },
  {
    species: "cat",
    breeds: [
      ["Domestic Shorthair", ["short coat", "lean build", "almond eyes"]],
      ["Maine Coon", ["long shaggy coat", "tufted ears", "large frame"]],
      ["Siamese", ["colorpoint coat", "blue eyes", "slender body"]],
      ["British Shorthair", ["dense plush coat", "round face", "stocky build"]],
      ["Bengal", ["spotted coat", "muscular build", "wild markings"]],
    ],
    ages: [[0, 0.5], [0.5, 2], [2, 10], [10, 16]],
  },
  {
    species: "rabbit",
    breeds: [
      ["Holland Lop", ["lopped ears", "compact body", "rounded head"]],
      ["Netherland Dwarf", ["tiny frame", "short ears", "round face"]],
      ["Flemish Giant", ["very large frame", "long ears", "dense coat"]],
    ],
    ages: [[0, 0.3], [0.3, 1], [1, 6], [6, 10]],
  },
] as const;

function confidence(value: number, low: number, high: number): number {
  return Number((low + (value / 255) * (high - low)).toFixed(4));
}

async function analyzeImage(bytes: Uint8Array) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const profile = SPECIES_PROFILES[digest[0] % SPECIES_PROFILES.length];
  const first = digest[2] % profile.breeds.length;
  const second = (first + 1 + digest[3] % (profile.breeds.length - 1)) % profile.breeds.length;
  const primaryConfidence = confidence(digest[4], 0.55, 0.93);
  const ageIndex = digest[6] % 4;
  const ageLabels = ["baby", "young", "adult", "senior"] as const;
  return {
    model_version: "mock-vision-0.3.0",
    species: profile.species,
    species_confidence: confidence(digest[1], 0.82, 0.99),
    breed_candidates: [
      { breed: profile.breeds[first][0], confidence: primaryConfidence },
      {
        breed: profile.breeds[second][0],
        confidence: Math.max(0.05, Math.min(primaryConfidence - 0.1, confidence(digest[5], 0.05, 0.35))),
      },
    ],
    age_estimate: {
      category: ageLabels[ageIndex],
      min_years: profile.ages[ageIndex][0],
      max_years: profile.ages[ageIndex][1],
      confidence: confidence(digest[7], 0.6, 0.9),
    },
    characteristics: [...profile.breeds[first][1]],
  };
}

async function handleAuth(request: Request, env: Env, path: string): Promise<Response | null> {
  if (path === "/v1/auth/signup" && request.method === "POST") {
    const body = await readJson<Record<string, unknown>>(request);
    const email = String(body.email ?? "").trim().toLowerCase();
    const password = String(body.password ?? "");
    const displayName = String(body.display_name ?? "").trim();
    const role = body.role === "veterinarian" ? "veterinarian" : "owner";
    if (!/^\S+@\S+\.\S+$/.test(email)) throw new HttpError(422, "Enter a valid email address.");
    if (password.length < 8 || password.length > 128) throw new HttpError(422, "Password must be 8–128 characters.");
    if (!displayName || displayName.length > 120) throw new HttpError(422, "Display name is required.");
    const duplicate = await env.DB.prepare("SELECT id FROM users WHERE lower(email) = ?").bind(email).first();
    if (duplicate) throw new HttpError(409, "An account with this email already exists.");
    const id = crypto.randomUUID();
    const createdAt = nowIso();
    await env.DB.prepare(
      `INSERT INTO users
       (id, email, password_hash, display_name, bio, avatar_url, role, clinic_name, license_number, created_at)
       VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)`,
    ).bind(
      id,
      email,
      await hashPassword(password),
      displayName,
      role,
      role === "veterinarian" ? String(body.clinic_name ?? "").trim() || null : null,
      role === "veterinarian" ? String(body.license_number ?? "").trim() || null : null,
      createdAt,
    ).run();
    const user = await userById(env, id);
    if (!user) throw new HttpError(500, "Account could not be created.");
    return json({ token: await createSession(env, id), user: publicUser(user) }, 201);
  }

  if (path === "/v1/auth/login" && request.method === "POST") {
    const body = await readJson<Record<string, unknown>>(request);
    const email = String(body.email ?? "").trim().toLowerCase();
    const user = await env.DB.prepare("SELECT * FROM users WHERE lower(email) = ?").bind(email).first<UserRow>();
    if (!user || !(await verifyPassword(String(body.password ?? ""), user.password_hash))) {
      throw new HttpError(401, "Incorrect email or password.");
    }
    return json({ token: await createSession(env, user.id), user: publicUser(user) });
  }

  if (path === "/v1/auth/me" && request.method === "GET") {
    return json(publicUser(await requireUser(request, env)));
  }
  return null;
}

async function handleUsers(request: Request, env: Env, path: string): Promise<Response | null> {
  if (path === "/v1/users/me" && request.method === "PATCH") {
    const user = await requireUser(request, env);
    const body = await readJson<Record<string, unknown>>(request);
    const displayName = body.display_name === undefined ? user.display_name : String(body.display_name).trim();
    const email = body.email === undefined ? user.email : String(body.email).trim().toLowerCase();
    if (!displayName) throw new HttpError(422, "Display name is required.");
    if (!/^\S+@\S+\.\S+$/.test(email)) throw new HttpError(422, "Enter a valid email address.");
    const taken = await env.DB.prepare("SELECT id FROM users WHERE lower(email) = ? AND id <> ?")
      .bind(email, user.id)
      .first();
    if (taken) throw new HttpError(409, "An account with this email already exists.");
    await env.DB.prepare(
      `UPDATE users SET display_name = ?, email = ?, bio = ?, clinic_name = ?, license_number = ? WHERE id = ?`,
    ).bind(
      displayName,
      email,
      body.bio === undefined ? user.bio : String(body.bio ?? "").trim() || null,
      body.clinic_name === undefined ? user.clinic_name : String(body.clinic_name ?? "").trim() || null,
      body.license_number === undefined ? user.license_number : String(body.license_number ?? "").trim() || null,
      user.id,
    ).run();
    return json(publicUser((await userById(env, user.id))!));
  }

  if (path === "/v1/users/me/password" && request.method === "POST") {
    const user = await requireUser(request, env);
    const body = await readJson<Record<string, unknown>>(request);
    if (!(await verifyPassword(String(body.current_password ?? ""), user.password_hash))) {
      throw new HttpError(401, "Current password is incorrect.");
    }
    const password = String(body.new_password ?? "");
    if (password.length < 8 || password.length > 128) throw new HttpError(422, "Password must be 8–128 characters.");
    await env.DB.prepare("UPDATE users SET password_hash = ? WHERE id = ?")
      .bind(await hashPassword(password), user.id)
      .run();
    return noContent();
  }

  if (path === "/v1/users/me/avatar" && request.method === "POST") {
    const user = await requireUser(request, env);
    const { file } = await uploadedFile(request);
    const stored = await storeImage(env, "avatars", file);
    await env.DB.prepare("UPDATE users SET avatar_url = ? WHERE id = ?").bind(stored.url, user.id).run();
    return json(publicUser((await userById(env, user.id))!));
  }
  return null;
}

async function handleAnimals(request: Request, env: Env, path: string): Promise<Response | null> {
  if (!path.startsWith("/v1/animals")) return null;
  const user = await requireUser(request, env);
  if (path === "/v1/animals" && request.method === "GET") {
    const rows = await env.DB.prepare("SELECT * FROM animals WHERE owner_id = ? ORDER BY created_at")
      .bind(user.id)
      .all<AnimalRow>();
    return json(rows.results.map(publicAnimal));
  }
  if (path === "/v1/animals" && request.method === "POST") {
    const body = await readJson<Record<string, unknown>>(request);
    const name = String(body.name ?? "").trim();
    const species = String(body.species ?? "").trim();
    if (!name || !species) throw new HttpError(422, "Pet name and species are required.");
    const id = crypto.randomUUID();
    await env.DB.prepare(
      `INSERT INTO animals
       (id, name, species, breed, birth_date, photo_url, photo_position_x, photo_position_y, photo_zoom, age_category, owner_id, created_at)
       VALUES (?, ?, ?, ?, ?, NULL, 50, 50, 1, 'unknown', ?, ?)`,
    ).bind(id, name, species, String(body.breed ?? "").trim() || null, body.birth_date || null, user.id, nowIso()).run();
    return json(publicAnimal(await ownedAnimal(env, id, user.id)), 201);
  }

  const match = path.match(/^\/v1\/animals\/([^/]+)(\/photo)?$/);
  if (!match) return null;
  const animalId = decodeURIComponent(match[1]);
  const animal = await ownedAnimal(env, animalId, user.id);
  if (match[2] === "/photo" && request.method === "POST") {
    const { file } = await uploadedFile(request);
    const stored = await storeImage(env, "pets", file);
    await env.DB.prepare(
      "UPDATE animals SET photo_url = ?, photo_position_x = 50, photo_position_y = 50, photo_zoom = 1 WHERE id = ?",
    ).bind(stored.url, animal.id).run();
    return json(publicAnimal(await ownedAnimal(env, animal.id, user.id)));
  }
  if (!match[2] && request.method === "GET") return json(publicAnimal(animal));
  if (!match[2] && request.method === "DELETE") {
    await env.DB.prepare("DELETE FROM animals WHERE id = ?").bind(animal.id).run();
    return noContent();
  }
  if (!match[2] && request.method === "PATCH") {
    const body = await readJson<Record<string, unknown>>(request);
    const name = body.name === undefined ? animal.name : String(body.name).trim();
    const species = body.species === undefined ? animal.species : String(body.species).trim();
    if (!name || !species) throw new HttpError(422, "Pet name and species are required.");
    const positionX = Math.min(100, Math.max(0, Number(body.photo_position_x ?? animal.photo_position_x)));
    const positionY = Math.min(100, Math.max(0, Number(body.photo_position_y ?? animal.photo_position_y)));
    const zoom = Math.min(3, Math.max(1, Number(body.photo_zoom ?? animal.photo_zoom)));
    await env.DB.prepare(
      `UPDATE animals SET name = ?, species = ?, breed = ?, birth_date = ?,
       photo_position_x = ?, photo_position_y = ?, photo_zoom = ? WHERE id = ?`,
    ).bind(
      name,
      species,
      body.breed === undefined ? animal.breed : String(body.breed ?? "").trim() || null,
      body.birth_date === undefined ? animal.birth_date : body.birth_date || null,
      positionX,
      positionY,
      zoom,
      animal.id,
    ).run();
    return json(publicAnimal(await ownedAnimal(env, animal.id, user.id)));
  }
  return null;
}

async function handlePosts(request: Request, env: Env, url: URL): Promise<Response | null> {
  const path = url.pathname;
  if (path === "/v1/posts" && request.method === "GET") {
    const limit = Math.min(100, Math.max(1, Number(url.searchParams.get("limit") ?? 20)));
    const offset = Math.max(0, Number(url.searchParams.get("offset") ?? 0));
    const rows = await env.DB.prepare(`${POST_SELECT} ORDER BY p.created_at DESC LIMIT ? OFFSET ?`)
      .bind(limit, offset)
      .all<Record<string, unknown>>();
    return json(rows.results.map(postFromJoined));
  }
  if (path === "/v1/posts" && request.method === "POST") {
    const body = await readJson<Record<string, unknown>>(request);
    const title = String(body.title ?? "").trim();
    const content = String(body.content ?? "").trim();
    if (!title || !content) throw new HttpError(422, "Title and content are required.");
    const actor = await currentUser(request, env) ?? (await userById(env, OWNER_ID));
    if (!actor) throw new HttpError(409, "No demo user is available.");
    const id = crypto.randomUUID();
    const created = nowIso();
    await env.DB.prepare(
      "INSERT INTO posts (id, title, content, author_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
    ).bind(id, title, content, actor.id, created, created).run();
    return json(await postDetail(env, id), 201);
  }
  const commentMatch = path.match(/^\/v1\/posts\/([^/]+)\/comments$/);
  if (commentMatch && request.method === "POST") {
    const postId = decodeURIComponent(commentMatch[1]);
    await postDetail(env, postId);
    const body = await readJson<Record<string, unknown>>(request);
    const content = String(body.content ?? "").trim();
    if (!content) throw new HttpError(422, "Comment is required.");
    const actor = await currentUser(request, env) ?? (await userById(env, OWNER_ID));
    if (!actor) throw new HttpError(409, "No demo user is available.");
    const id = crypto.randomUUID();
    const createdAt = nowIso();
    await env.DB.prepare(
      "INSERT INTO comments (id, post_id, author_id, content, created_at) VALUES (?, ?, ?, ?, ?)",
    ).bind(id, postId, actor.id, content, createdAt).run();
    return json({ id, content, author: publicUser(actor), created_at: createdAt }, 201);
  }
  const detailMatch = path.match(/^\/v1\/posts\/([^/]+)$/);
  if (detailMatch && request.method === "GET") return json(await postDetail(env, decodeURIComponent(detailMatch[1])));
  return null;
}

async function handleAnalysis(request: Request, env: Env, path: string): Promise<Response | null> {
  if (path !== "/v1/analysis/upload" || request.method !== "POST") return null;
  const { form, file } = await uploadedFile(request);
  const animalId = String(form.get("animal_id") ?? "").trim() || null;
  if (animalId) {
    const animal = await env.DB.prepare("SELECT id FROM animals WHERE id = ?").bind(animalId).first();
    if (!animal) throw new HttpError(404, `Animal ${animalId} not found.`);
  }
  const stored = await storeImage(env, "uploads", file);
  const result = await analyzeImage(stored.bytes);
  const id = crypto.randomUUID();
  const createdAt = nowIso();
  await env.DB.prepare(
    `INSERT INTO ai_analysis_logs
     (id, animal_id, image_key, image_url, model_version, species, species_confidence, result_json, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    id,
    animalId,
    stored.key,
    stored.url,
    result.model_version,
    result.species,
    result.species_confidence,
    JSON.stringify(result),
    createdAt,
  ).run();
  return json({ analysis_id: id, animal_id: animalId, image_url: stored.url, created_at: createdAt, result }, 201);
}

async function handleMedia(request: Request, env: Env, path: string): Promise<Response> {
  if (request.method !== "GET" && request.method !== "HEAD") return new Response(null, { status: 405 });
  const key = path.slice("/media/".length).split("/").map(decodeURIComponent).join("/");
  const object = await env.MEDIA.get(key);
  if (!object) return new Response("Not found", { status: 404 });
  const headers = new Headers({ "cache-control": "public, max-age=31536000, immutable", etag: object.httpEtag });
  object.writeHttpMetadata(headers);
  return new Response(request.method === "HEAD" ? null : object.body, { headers });
}

async function routeApi(request: Request, env: Env, url: URL): Promise<Response> {
  await ensureDatabase(env);
  const handlers = [
    () => handleAuth(request, env, url.pathname),
    () => handleUsers(request, env, url.pathname),
    () => handleAnimals(request, env, url.pathname),
    () => handlePosts(request, env, url),
    () => handleAnalysis(request, env, url.pathname),
  ];
  for (const handler of handlers) {
    const response = await handler();
    if (response) return response;
  }
  if (url.pathname === "/v1/vets" && request.method === "GET") {
    const rows = await env.DB.prepare("SELECT * FROM users WHERE role = 'veterinarian' ORDER BY display_name").all<UserRow>();
    return json(rows.results.map(publicUser));
  }
  throw new HttpError(404, "Endpoint not found.");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/healthz") return json({ status: "ok", service: "UEP EMMY" });
      if (url.pathname.startsWith("/media/")) return handleMedia(request, env, url.pathname);
      if (url.pathname.startsWith("/v1/")) return routeApi(request, env, url);
      return new Response(null, { status: 404 });
    } catch (error) {
      if (error instanceof HttpError) return json({ detail: error.message }, error.status);
      console.error(error);
      return json({ detail: "Unexpected server error." }, 500);
    }
  },
};
