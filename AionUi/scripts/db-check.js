/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Database health check script
 */

require('dotenv').config();
const { Pool } = require('pg');

const connectionString =
  process.env.DATABASE_URL || 'postgresql://hivemind:hivemind_dev_password@localhost:5432/hivemind';

const pool = new Pool({ connectionString });

async function checkDatabase() {
  console.log('🔍 Checking database connection...\n');

  try {
    // Test connection
    const client = await pool.connect();
    console.log('✅ Connection successful');

    // Check database version
    const versionResult = await client.query('SELECT version()');
    console.log('\n📦 PostgreSQL Version:');
    console.log(versionResult.rows[0].version.split(',')[0]);

    // Check current database
    const dbResult = await client.query('SELECT current_database()');
    console.log('\n🗄️  Current Database:', dbResult.rows[0].current_database);

    // Check tables
    const tablesResult = await client.query(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'public'
      ORDER BY table_name
    `);

    console.log('\n📋 Tables (' + tablesResult.rows.length + '):');
    tablesResult.rows.forEach((row) => {
      console.log('  - ' + row.table_name);
    });

    // Check table sizes
    const sizeResult = await client.query(`
      SELECT
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
      FROM pg_tables
      WHERE schemaname = 'public'
      ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
      LIMIT 10
    `);

    if (sizeResult.rows.length > 0) {
      console.log('\n💾 Table Sizes (Top 10):');
      sizeResult.rows.forEach((row) => {
        console.log(`  - ${row.tablename}: ${row.size}`);
      });
    }

    // Check connection pool stats
    console.log('\n🔌 Connection Pool:');
    console.log('  - Total connections:', pool.totalCount);
    console.log('  - Idle connections:', pool.idleCount);
    console.log('  - Waiting requests:', pool.waitingCount);

    client.release();

    console.log('\n✅ Database health check passed!\n');
    process.exit(0);
  } catch (error) {
    console.error('\n❌ Database health check failed:');
    console.error(error.message);
    console.error('\nPlease ensure:');
    console.error('  1. PostgreSQL is running (docker-compose up -d postgres)');
    console.error('  2. DATABASE_URL is correct in .env');
    console.error('  3. Database credentials are valid\n');
    process.exit(1);
  } finally {
    await pool.end();
  }
}

checkDatabase();
