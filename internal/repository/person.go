// Package repository — PersonRepo handles database operations for persons.
// Persons track people you lend to or borrow from (like a contact ledger).
package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/ahmedelsamadisi/clearmoney/internal/models"
)

// PersonRepo handles database operations for persons.
type PersonRepo struct {
	db *sql.DB
}

func NewPersonRepo(db *sql.DB) *PersonRepo {
	return &PersonRepo{db: db}
}

// Create inserts a new person.
func (r *PersonRepo) Create(ctx context.Context, p models.Person) (models.Person, error) {
	err := r.db.QueryRowContext(ctx, `
		INSERT INTO persons (name, note, net_balance)
		VALUES ($1, $2, $3)
		RETURNING id, created_at, updated_at
	`, p.Name, p.Note, p.NetBalance).Scan(&p.ID, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return models.Person{}, fmt.Errorf("inserting person: %w", err)
	}
	return p, nil
}

// GetByID retrieves a single person.
func (r *PersonRepo) GetByID(ctx context.Context, id string) (models.Person, error) {
	var p models.Person
	err := r.db.QueryRowContext(ctx, `
		SELECT id, name, note, net_balance, created_at, updated_at
		FROM persons WHERE id = $1
	`, id).Scan(&p.ID, &p.Name, &p.Note, &p.NetBalance, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return models.Person{}, fmt.Errorf("getting person: %w", err)
	}
	return p, nil
}

// GetAll retrieves all persons ordered by name.
func (r *PersonRepo) GetAll(ctx context.Context) ([]models.Person, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT id, name, note, net_balance, created_at, updated_at
		FROM persons ORDER BY name
	`)
	if err != nil {
		return nil, fmt.Errorf("querying persons: %w", err)
	}
	defer rows.Close()

	var persons []models.Person
	for rows.Next() {
		var p models.Person
		if err := rows.Scan(&p.ID, &p.Name, &p.Note, &p.NetBalance, &p.CreatedAt, &p.UpdatedAt); err != nil {
			return nil, fmt.Errorf("scanning person: %w", err)
		}
		persons = append(persons, p)
	}
	return persons, rows.Err()
}

// Update modifies a person's name and note.
func (r *PersonRepo) Update(ctx context.Context, p models.Person) (models.Person, error) {
	err := r.db.QueryRowContext(ctx, `
		UPDATE persons SET name = $2, note = $3, updated_at = now()
		WHERE id = $1
		RETURNING id, name, note, net_balance, created_at, updated_at
	`, p.ID, p.Name, p.Note).Scan(&p.ID, &p.Name, &p.Note, &p.NetBalance, &p.CreatedAt, &p.UpdatedAt)
	if err != nil {
		return models.Person{}, fmt.Errorf("updating person: %w", err)
	}
	return p, nil
}

// Delete removes a person.
func (r *PersonRepo) Delete(ctx context.Context, id string) error {
	result, err := r.db.ExecContext(ctx, `DELETE FROM persons WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("deleting person: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

// UpdateNetBalanceTx adjusts a person's net_balance within a DB transaction.
func (r *PersonRepo) UpdateNetBalanceTx(ctx context.Context, dbTx *sql.Tx, personID string, delta float64) error {
	result, err := dbTx.ExecContext(ctx, `
		UPDATE persons SET net_balance = net_balance + $2, updated_at = now()
		WHERE id = $1
	`, personID, delta)
	if err != nil {
		return fmt.Errorf("updating person balance: %w", err)
	}
	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return sql.ErrNoRows
	}
	return nil
}
