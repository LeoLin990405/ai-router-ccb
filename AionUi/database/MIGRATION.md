# Database Migration Guide

This guide covers database schema migrations using Drizzle Kit.

## Migration Workflow

### 1. Schema Changes

Modify schema files in `src/database/schema/`:

```typescript
// Example: Add new field to users table
export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  username: varchar('username', { length: 100 }).notNull().unique(),
  // ... existing fields
  newField: text('new_field'), // Add new field
});
```

### 2. Generate Migration

Generate a migration file from schema changes:

```bash
npm run db:generate
```

This creates a new SQL migration file in `database/migrations/` with a timestamp.

### 3. Review Migration

Review the generated SQL migration file:

```sql
-- Example: database/migrations/0001_add_new_field.sql
ALTER TABLE "users" ADD COLUMN "new_field" text;
```

**Important**: Always review migrations before applying them to ensure they match your intentions.

### 4. Apply Migration

Run migrations on your database:

```bash
npm run db:migrate
```

This applies all pending migrations in order.

## Development vs Production

### Development (Schema Push)

For rapid development, you can push schema changes directly without generating migration files:

```bash
npm run db:push
```

**Warning**: This bypasses migration history. Use only in development.

### Production (Migrations)

Always use migrations in production:

```bash
# 1. Generate migration
npm run db:generate

# 2. Review migration file
cat database/migrations/XXXXXX_migration_name.sql

# 3. Apply migration
npm run db:migrate
```

## Common Migration Scenarios

### Adding a Column

```typescript
// Schema change
export const users = pgTable('users', {
  // ... existing fields
  phoneNumber: varchar('phone_number', { length: 20 }),
});
```

Generated SQL:
```sql
ALTER TABLE "users" ADD COLUMN "phone_number" varchar(20);
```

### Renaming a Column

```typescript
// Drizzle doesn't auto-generate renames, manually create migration
```

Manual migration:
```sql
ALTER TABLE "users" RENAME COLUMN "old_name" TO "new_name";
```

### Adding an Index

```typescript
export const users = pgTable(
  'users',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    email: varchar('email', { length: 255 }).notNull(),
  },
  (table) => ({
    emailIdx: index('users_email_idx').on(table.email),
  })
);
```

Generated SQL:
```sql
CREATE INDEX "users_email_idx" ON "users" ("email");
```

### Adding a Foreign Key

```typescript
export const posts = pgTable('posts', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: uuid('user_id')
    .notNull()
    .references(() => users.id, { onDelete: 'cascade' }),
});
```

Generated SQL:
```sql
ALTER TABLE "posts" ADD CONSTRAINT "posts_user_id_users_id_fk"
  FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE;
```

### Dropping a Column

```typescript
// Remove field from schema, then generate migration
```

Generated SQL:
```sql
ALTER TABLE "users" DROP COLUMN "old_field";
```

## Migration Commands

| Command | Description |
|---------|-------------|
| `npm run db:generate` | Generate migration from schema changes |
| `npm run db:migrate` | Apply pending migrations |
| `npm run db:push` | Push schema directly (dev only) |
| `npm run db:studio` | Open Drizzle Studio GUI |
| `npm run db:drop` | Drop all database objects |

## Rollback Strategy

Drizzle Kit doesn't have built-in rollback. For rollbacks:

### Option 1: Manual Rollback

Create a reverse migration manually:

```sql
-- Original migration
ALTER TABLE "users" ADD COLUMN "new_field" text;

-- Rollback migration
ALTER TABLE "users" DROP COLUMN "new_field";
```

### Option 2: Database Backup

Before applying migrations in production:

```bash
# Backup
pg_dump -U hivemind -d hivemind > backup.sql

# Apply migration
npm run db:migrate

# If needed, restore
psql -U hivemind -d hivemind < backup.sql
```

### Option 3: Snapshot Restore

Use PostgreSQL snapshots for quick rollback:

```sql
-- Create snapshot
CREATE SCHEMA snapshot;
CREATE TABLE snapshot.backup AS SELECT * FROM users;

-- Restore if needed
TRUNCATE users;
INSERT INTO users SELECT * FROM snapshot.backup;
```

## Migration Best Practices

1. **Always review** generated migrations before applying
2. **Test migrations** on development database first
3. **Backup production** before applying migrations
4. **Small migrations** - one logical change per migration
5. **Descriptive names** - use clear migration names
6. **No data changes** - keep data migrations separate
7. **Avoid breaking changes** - use multi-step migrations for renames

## Multi-Step Migrations

For breaking changes, use multiple migrations:

### Example: Renaming a column

**Step 1**: Add new column
```sql
ALTER TABLE "users" ADD COLUMN "full_name" text;
UPDATE "users" SET "full_name" = "name";
```

**Step 2**: Deploy application code that uses both columns

**Step 3**: Drop old column
```sql
ALTER TABLE "users" DROP COLUMN "name";
```

## Data Migrations

For complex data transformations, create separate scripts:

```typescript
// scripts/migrate-data-001.ts
import { db } from '../src/database/db';

async function migrateData() {
  // Complex data transformation
  const users = await db.select().from(users);

  for (const user of users) {
    // Transform and update
    await db.update(users).set({
      // ... transformed data
    }).where(eq(users.id, user.id));
  }
}

migrateData().then(() => {
  console.log('Data migration complete');
  process.exit(0);
});
```

Run data migrations separately:
```bash
node scripts/migrate-data-001.ts
```

## Initial Migration

The initial migration creates all tables, indexes, and constraints. It was generated from the complete schema definition.

To regenerate from scratch:

```bash
# 1. Drop all migrations
npm run db:drop

# 2. Delete migration files
rm -rf database/migrations/*

# 3. Generate fresh migration
npm run db:generate

# 4. Apply migration
npm run db:migrate
```

## Troubleshooting

### Migration failed

Check the error message and review the migration SQL. Common issues:

- Column already exists: Remove from schema or delete migration
- Foreign key violation: Ensure referenced tables exist first
- Type mismatch: Check data types in schema

### Out of sync

If schema and database are out of sync:

```bash
# Development: Push schema directly
npm run db:push

# Production: Generate and apply migration
npm run db:generate
npm run db:migrate
```

### Drizzle Kit issues

Clear Drizzle meta cache:

```bash
rm -rf drizzle
npm run db:generate
```

## Schema Introspection

Pull existing database schema:

```bash
drizzle-kit introspect:pg
```

This generates TypeScript schema from existing database.

## Version Control

- **Commit migrations** to version control
- **Never modify** applied migrations
- **Use timestamps** in migration names for ordering
- **Tag releases** with migration status

## Monitoring

Check migration status:

```bash
# Connect to database
psql -U hivemind -d hivemind

# Check drizzle migrations table
SELECT * FROM __drizzle_migrations;
```

## Further Reading

- [Drizzle Kit Documentation](https://orm.drizzle.team/kit-docs/overview)
- [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)
- [Database Migration Best Practices](https://www.postgresql.org/docs/current/ddl.html)
