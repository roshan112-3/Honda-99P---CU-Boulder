// ============================================================================
// Honda 99P Knowledge Graph — Neo4j Schema
// ============================================================================
// Run this ONCE to set up constraints and indexes.
// Constraints implicitly create unique indexes.
//
// Usage:
//   cat schema.cypher | cypher-shell -u neo4j -p honda99p
//   OR paste into Neo4j Browser
// ============================================================================

// ---------------------------------------------------------------------------
// 1. UNIQUENESS CONSTRAINTS (also serve as primary lookups)
// ---------------------------------------------------------------------------

CREATE CONSTRAINT file_path_unique IF NOT EXISTS
  FOR (f:File) REQUIRE f.path IS UNIQUE;

CREATE CONSTRAINT function_uid_unique IF NOT EXISTS
  FOR (fn:Function) REQUIRE fn.uid IS UNIQUE;

CREATE CONSTRAINT class_name_file_unique IF NOT EXISTS
  FOR (c:Class) REQUIRE (c.name, c.file) IS UNIQUE;

CREATE CONSTRAINT commit_sha_unique IF NOT EXISTS
  FOR (cm:Commit) REQUIRE cm.sha IS UNIQUE;

CREATE CONSTRAINT author_name_unique IF NOT EXISTS
  FOR (a:Author) REQUIRE a.name IS UNIQUE;

CREATE CONSTRAINT hsi_field_name_unique IF NOT EXISTS
  FOR (h:HSIField) REQUIRE h.name IS UNIQUE;

// ---------------------------------------------------------------------------
// 2. COMPOSITE / RANGE INDEXES (for traversal queries)
// ---------------------------------------------------------------------------

// Fast lookup of functions by file (risk propagation entry point)
CREATE INDEX function_file_idx IF NOT EXISTS
  FOR (fn:Function) ON (fn.file);

// Fast lookup by language (filtering)
CREATE INDEX function_language_idx IF NOT EXISTS
  FOR (fn:Function) ON (fn.language);

// Fast lookup of classes by file
CREATE INDEX class_file_idx IF NOT EXISTS
  FOR (c:Class) ON (c.file);

// Commit timestamp for temporal queries
CREATE INDEX commit_timestamp_idx IF NOT EXISTS
  FOR (cm:Commit) ON (cm.timestamp);

// File language for filtering
CREATE INDEX file_language_idx IF NOT EXISTS
  FOR (f:File) ON (f.language);

// ---------------------------------------------------------------------------
// 3. FULL-TEXT INDEXES (for RAG similarity search later)
// ---------------------------------------------------------------------------

CREATE FULLTEXT INDEX function_name_fulltext IF NOT EXISTS
  FOR (fn:Function) ON EACH [fn.name, fn.full_name];

CREATE FULLTEXT INDEX commit_message_fulltext IF NOT EXISTS
  FOR (cm:Commit) ON EACH [cm.message];
