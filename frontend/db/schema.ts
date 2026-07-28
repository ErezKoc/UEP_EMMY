import { index, integer, real, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const users = sqliteTable(
  "users",
  {
    id: text("id").primaryKey(),
    email: text("email").notNull(),
    passwordHash: text("password_hash").notNull(),
    displayName: text("display_name").notNull(),
    bio: text("bio"),
    avatarUrl: text("avatar_url"),
    role: text("role").notNull(),
    clinicName: text("clinic_name"),
    licenseNumber: text("license_number"),
    createdAt: text("created_at").notNull(),
  },
  (table) => [uniqueIndex("users_email_idx").on(table.email), index("users_role_idx").on(table.role)],
);

export const sessions = sqliteTable(
  "sessions",
  {
    token: text("token").primaryKey(),
    userId: text("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    expiresAt: integer("expires_at").notNull(),
  },
  (table) => [index("sessions_user_idx").on(table.userId)],
);

export const animals = sqliteTable(
  "animals",
  {
    id: text("id").primaryKey(),
    name: text("name").notNull(),
    species: text("species").notNull(),
    breed: text("breed"),
    birthDate: text("birth_date"),
    photoUrl: text("photo_url"),
    photoPositionX: integer("photo_position_x").notNull().default(50),
    photoPositionY: integer("photo_position_y").notNull().default(50),
    photoZoom: real("photo_zoom").notNull().default(1),
    ageCategory: text("age_category").notNull().default("unknown"),
    ownerId: text("owner_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("animals_owner_idx").on(table.ownerId)],
);

export const analysisLogs = sqliteTable(
  "ai_analysis_logs",
  {
    id: text("id").primaryKey(),
    userId: text("user_id").references(() => users.id, { onDelete: "set null" }),
    animalId: text("animal_id").references(() => animals.id, { onDelete: "set null" }),
    imageKey: text("image_key").notNull(),
    imageUrl: text("image_url").notNull(),
    modelVersion: text("model_version").notNull(),
    species: text("species").notNull(),
    speciesConfidence: real("species_confidence").notNull(),
    result: text("result_json").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("analysis_created_idx").on(table.createdAt),
    index("analysis_user_idx").on(table.userId),
  ],
);

export const posts = sqliteTable(
  "posts",
  {
    id: text("id").primaryKey(),
    title: text("title").notNull(),
    content: text("content").notNull(),
    authorId: text("author_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    analysisId: text("analysis_id").references(() => analysisLogs.id, { onDelete: "set null" }),
    imageUrl: text("image_url"),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    index("posts_created_idx").on(table.createdAt),
    index("posts_analysis_idx").on(table.analysisId),
  ],
);

export const comments = sqliteTable(
  "comments",
  {
    id: text("id").primaryKey(),
    postId: text("post_id").notNull().references(() => posts.id, { onDelete: "cascade" }),
    authorId: text("author_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    content: text("content").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("comments_post_idx").on(table.postId)],
);
