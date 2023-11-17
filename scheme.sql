CREATE TABLE league_settings (
    week_number INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    value VARCHAR(255) NOT NULL
);

CREATE UNIQUE INDEX unique_league_settings ON league_settings(week_number, name, value);
