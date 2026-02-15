# HiveMind Database

PostgreSQL database setup with Drizzle ORM for HiveMind project.

## Quick Start

### 1. Start Database

```bash
# Start PostgreSQL and Redis with Docker Compose
docker-compose up -d postgres redis

# Verify containers are running
docker-compose ps

# Check logs
docker-compose logs -f postgres
```

### 2. Run Migrations

```bash
# Generate migration files from schema
npm run db:generate

# Push changes to database
npm run db:push

# Or apply migrations
npm run db:migrate
```

### 3. Seed Development Data

```bash
npm run db:seed
```

### 4. Access Database

**Using psql:**
```bash
# Connect to database
docker exec -it hivemind-postgres psql -U hivemind -d hivemind

# Or from host
psql postgresql://hivemind:hivemind_dev_password@localhost:5432/hivemind
```

**Using pgAdmin:**
```bash
# Start pgAdmin (optional)
docker-compose --profile tools up -d pgadmin

# Open browser: http://localhost:5050
# Login: admin@hivemind.local / admin
# Add server: postgres:5432, user: hivemind
```

## Database Structure

### Core Tables

- `users` - User accounts and authentication
- `refresh_tokens` - JWT refresh tokens
- `conversations` - AI conversation sessions
- `messages` - Conversation messages
- `providers` - AI provider configurations
- `models` - AI model definitions

### Extension Tables (To be added)

- `skills` - Installed skills
- `cron_jobs` - Scheduled tasks
- `mcp_servers` - MCP server configurations
- `channels` - Multi-agent communication channels
- `teams` - Agent team configurations
- `files` - File metadata

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
DATABASE_URL=postgresql://hivemind:hivemind_dev_password@localhost:5432/hivemind
POSTGRES_PASSWORD=hivemind_dev_password
```

## Migration Workflow

```bash
# 1. Update schema files in src/database/schema/
# 2. Generate migration
npm run db:generate

# 3. Review generated migration in database/migrations/
# 4. Apply migration
npm run db:migrate

# Or use push for development (no migration files)
npm run db:push
```

## Drizzle Studio

Visual database browser:

```bash
npm run db:studio

# Opens at http://localhost:4983
```

## Backup & Restore

### Backup

```bash
# Backup database
docker exec hivemind-postgres pg_dump -U hivemind hivemind > backup.sql

# Or use npm script
npm run db:backup
```

### Restore

```bash
# Restore from backup
docker exec -i hivemind-postgres psql -U hivemind hivemind < backup.sql

# Or use npm script
npm run db:restore -- backup.sql
```

## Connection Pooling

- **Max connections**: 20
- **Idle timeout**: 30 seconds
- **Connection timeout**: 10 seconds

Configured in `src/database/db.ts`

## Health Check

```bash
# Check database connection
npm run db:check
```

## Troubleshooting

### Connection refused

```bash
# Check if postgres is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart postgres
docker-compose restart postgres
```

### Reset database

```bash
# WARNING: This deletes all data
docker-compose down -v
docker-compose up -d postgres
npm run db:push
npm run db:seed
```

### Port already in use

```bash
# Change port in docker-compose.yml:
ports:
  - '5433:5432'  # Use 5433 instead of 5432

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://hivemind:hivemind_dev_password@localhost:5433/hivemind
```

## Performance Tips

1. **Use connection pooling** - Already configured
2. **Add indexes** - Defined in schema files
3. **Use prepared statements** - Drizzle handles this automatically
4. **Monitor slow queries** - Check PostgreSQL logs

## Resources

- [Drizzle ORM Documentation](https://orm.drizzle.team/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
