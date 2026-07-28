ALTER TABLE `ai_analysis_logs` ADD `user_id` text REFERENCES users(id) ON DELETE SET NULL;--> statement-breakpoint
CREATE INDEX `analysis_user_idx` ON `ai_analysis_logs` (`user_id`);--> statement-breakpoint
ALTER TABLE `posts` ADD `analysis_id` text REFERENCES ai_analysis_logs(id) ON DELETE SET NULL;--> statement-breakpoint
ALTER TABLE `posts` ADD `image_url` text;--> statement-breakpoint
CREATE INDEX `posts_analysis_idx` ON `posts` (`analysis_id`);
