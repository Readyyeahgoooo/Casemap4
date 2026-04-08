// Core uniqueness constraints
CREATE CONSTRAINT module_id IF NOT EXISTS FOR (n:Module) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT subground_id IF NOT EXISTS FOR (n:Subground) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (n:Topic) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT topic_path IF NOT EXISTS FOR (n:Topic) REQUIRE n.path IS UNIQUE;
CREATE CONSTRAINT lineage_id IF NOT EXISTS FOR (n:AuthorityLineage) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT statute_id IF NOT EXISTS FOR (n:Statute) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT paragraph_id IF NOT EXISTS FOR (n:Paragraph) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT proposition_id IF NOT EXISTS FOR (n:Proposition) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT judge_id IF NOT EXISTS FOR (n:Judge) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:SourceDocument) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT case_neutral_citation IF NOT EXISTS FOR (n:Case) REQUIRE n.neutral_citation IS UNIQUE;
CREATE CONSTRAINT statute_cap_section_key IF NOT EXISTS FOR (n:Statute) REQUIRE n.cap_section_key IS UNIQUE;

// Search indexes
CREATE INDEX case_name IF NOT EXISTS FOR (n:Case) ON (n.case_name);
CREATE INDEX case_court_code IF NOT EXISTS FOR (n:Case) ON (n.court_code);
CREATE INDEX case_decision_date IF NOT EXISTS FOR (n:Case) ON (n.decision_date);
CREATE INDEX topic_label_en IF NOT EXISTS FOR (n:Topic) ON (n.label_en);

// Vector indexes
CREATE VECTOR INDEX case_summary_embedding IF NOT EXISTS
FOR (n:Case) ON (n.summary_embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX paragraph_embedding IF NOT EXISTS
FOR (n:Paragraph) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
