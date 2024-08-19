DROP INDEX league_settings_unique_flag;
DROP INDEX league_settings_unique_value;
ALTER TABLE league_settings
ADD COLUMN date DATE;
UPDATE league_settings
SET date = DATE(
    '2023-01-01',
    printf('%d days', (week_number - 1) * 7 - 3)
) WHERE week_number > 40;
UPDATE league_settings
SET date = DATE(
    '2024-01-01',
    printf('%d days', (week_number - 1) * 7 - 3)
) WHERE week_number < 40;
ALTER TABLE league_settings DROP COLUMN week_number;
CREATE UNIQUE INDEX "league_settings_unique_flag" ON "league_settings" (
	"date",
	"name"
);

CREATE UNIQUE INDEX "league_settings_unique_value" ON "league_settings" (
	"date",
	"value"
);
