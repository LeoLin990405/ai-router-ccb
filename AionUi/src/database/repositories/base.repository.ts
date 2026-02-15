/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 *
 * Base repository with common CRUD operations
 */

import { SQL, eq, and } from 'drizzle-orm';
import { PgTable } from 'drizzle-orm/pg-core';
import { db } from '../db';

export abstract class BaseRepository<T extends PgTable> {
  constructor(protected table: T) {}

  /**
   * Find all records with optional filters
   */
  async findAll(where?: SQL): Promise<any[]> {
    const query = db.select().from(this.table);
    if (where) {
      return query.where(where);
    }
    return query;
  }

  /**
   * Find a single record by ID
   */
  async findById(id: string): Promise<any | null> {
    const idColumn = this.table.id as any;
    const results = await db
      .select()
      .from(this.table)
      .where(eq(idColumn, id))
      .limit(1);
    return results[0] || null;
  }

  /**
   * Find a single record by conditions
   */
  async findOne(where: SQL): Promise<any | null> {
    const results = await db.select().from(this.table).where(where).limit(1);
    return results[0] || null;
  }

  /**
   * Create a new record
   */
  async create(data: any): Promise<any> {
    const results = await db.insert(this.table).values(data).returning();
    return results[0];
  }

  /**
   * Create multiple records
   */
  async createMany(data: any[]): Promise<any[]> {
    return db.insert(this.table).values(data).returning();
  }

  /**
   * Update a record by ID
   */
  async updateById(id: string, data: any): Promise<any | null> {
    const idColumn = this.table.id as any;
    const results = await db
      .update(this.table)
      .set(data)
      .where(eq(idColumn, id))
      .returning();
    return results[0] || null;
  }

  /**
   * Update records by conditions
   */
  async update(where: SQL, data: any): Promise<any[]> {
    return db.update(this.table).set(data).where(where).returning();
  }

  /**
   * Delete a record by ID
   */
  async deleteById(id: string): Promise<boolean> {
    const idColumn = this.table.id as any;
    const results = await db.delete(this.table).where(eq(idColumn, id)).returning();
    return results.length > 0;
  }

  /**
   * Delete records by conditions
   */
  async delete(where: SQL): Promise<number> {
    const results = await db.delete(this.table).where(where).returning();
    return results.length;
  }

  /**
   * Count records
   */
  async count(where?: SQL): Promise<number> {
    const query = db.select().from(this.table);
    const results = where ? await query.where(where) : await query;
    return results.length;
  }

  /**
   * Check if record exists
   */
  async exists(where: SQL): Promise<boolean> {
    const count = await this.count(where);
    return count > 0;
  }
}
