-- Tables for aspect mining baseline (!214)

BEGIN;

    -- Activate extensions for fuzzy search
    CREATE EXTENSION fuzzystrmatch;
    CREATE EXTENSION pg_trgm;


    -- Create tables
    CREATE TABLE absa.target_aspect (
        aspect_id SERIAL PRIMARY KEY,
        aspect text[]
    );

    CREATE TABLE absa.target_aspect_word (
        aspect_id int REFERENCES absa.target_aspect,
        word text,
        PRIMARY KEY (aspect_id, word)
    );

    CREATE TABLE absa.post_aspect (
        source TEXT,
        post_id TEXT,
        word_index INT,
        FOREIGN KEY (source, post_id, word_index) REFERENCES absa.post_word,
        aspect_id INT REFERENCES absa.target_aspect,
        target_aspect_word TEXT,
        FOREIGN KEY (aspect_id, target_aspect_word)
            REFERENCES absa.target_aspect_word(aspect_id, word),
        match_algorithm TEXT,
        PRIMARY KEY (match_algorithm, source, post_id, word_index, aspect_id)
    );

COMMIT;
