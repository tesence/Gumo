CREATE TABLE "league_settings" (
	"week_number"	INTEGER NOT NULL,
	"name"	VARCHAR(255) NOT NULL,
	"value"	VARCHAR(255) NOT NULL
);

CREATE UNIQUE INDEX "league_settings_unique_flag" ON "league_settings" (
	"week_number",
	"name"
);

CREATE UNIQUE INDEX "league_settings_unique_value" ON "league_settings" (
	"week_number",
	"value"
);
