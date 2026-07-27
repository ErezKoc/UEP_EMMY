CREATE TABLE `ai_analysis_logs` (
	`id` text PRIMARY KEY NOT NULL,
	`animal_id` text,
	`image_key` text NOT NULL,
	`image_url` text NOT NULL,
	`model_version` text NOT NULL,
	`species` text NOT NULL,
	`species_confidence` real NOT NULL,
	`result_json` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`animal_id`) REFERENCES `animals`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `analysis_created_idx` ON `ai_analysis_logs` (`created_at`);--> statement-breakpoint
CREATE TABLE `animals` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`species` text NOT NULL,
	`breed` text,
	`birth_date` text,
	`photo_url` text,
	`photo_position_x` integer DEFAULT 50 NOT NULL,
	`photo_position_y` integer DEFAULT 50 NOT NULL,
	`photo_zoom` real DEFAULT 1 NOT NULL,
	`age_category` text DEFAULT 'unknown' NOT NULL,
	`owner_id` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`owner_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `animals_owner_idx` ON `animals` (`owner_id`);--> statement-breakpoint
CREATE TABLE `comments` (
	`id` text PRIMARY KEY NOT NULL,
	`post_id` text NOT NULL,
	`author_id` text NOT NULL,
	`content` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`post_id`) REFERENCES `posts`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`author_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `comments_post_idx` ON `comments` (`post_id`);--> statement-breakpoint
CREATE TABLE `posts` (
	`id` text PRIMARY KEY NOT NULL,
	`title` text NOT NULL,
	`content` text NOT NULL,
	`author_id` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`author_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `posts_created_idx` ON `posts` (`created_at`);--> statement-breakpoint
CREATE TABLE `sessions` (
	`token` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`expires_at` integer NOT NULL,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `sessions_user_idx` ON `sessions` (`user_id`);--> statement-breakpoint
CREATE TABLE `users` (
	`id` text PRIMARY KEY NOT NULL,
	`email` text NOT NULL,
	`password_hash` text NOT NULL,
	`display_name` text NOT NULL,
	`bio` text,
	`avatar_url` text,
	`role` text NOT NULL,
	`clinic_name` text,
	`license_number` text,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_email_idx` ON `users` (`email`);--> statement-breakpoint
CREATE INDEX `users_role_idx` ON `users` (`role`);