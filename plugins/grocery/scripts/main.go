// Package main implements the Schnucks store data harvester.
// It fetches coupons and the full item catalog from the Schnucks API
// and stores them in a local SQLite database for offline deal analysis.
package main

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	_ "modernc.org/sqlite"
)

// ============================================================================
// Constants
// ============================================================================

const (
	baseURL      = "https://api.schnucks.com"
	requestDelay = 300 * time.Millisecond
	httpTimeout  = 30 * time.Second
	pageSize     = 100
)

// ============================================================================
// Configuration
// ============================================================================

// Config holds all runtime configuration loaded from environment variables.
type Config struct {
	AuthToken  string
	ClientID   string
	ClientType string
	StoreID    string
	DBPath     string
}

// loadEnv parses a .env file and sets each key=value pair as an environment variable.
// Blank lines and lines beginning with # are ignored.
func loadEnv(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open %s: %w", path, err)
	}
	defer func() { _ = f.Close() }()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, val, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		if err := os.Setenv(strings.TrimSpace(key), strings.TrimSpace(val)); err != nil {
			return fmt.Errorf("setenv %s: %w", key, err)
		}
	}
	return scanner.Err()
}

// mustEnv returns the value of the named environment variable.
// It writes an error to stderr and exits if the variable is unset or empty.
func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		fmt.Fprintf(os.Stderr, "ERROR: required env var %s is not set — see scripts/token_refresh.md\n", key)
		os.Exit(1)
	}
	return v
}

// loadConfig builds a Config from environment variables.
// DBPath overrides SCHNUCKS_DB_PATH when non-empty.
func loadConfig(dbPath string) *Config {
	if p := os.Getenv("SCHNUCKS_DB_PATH"); p != "" && dbPath == "" {
		dbPath = p
	}
	storeID := os.Getenv("SCHNUCKS_STORE_ID")
	if storeID == "" {
		storeID = "144"
	}
	clientType := os.Getenv("SCHNUCKS_CLIENT_TYPE")
	if clientType == "" {
		clientType = "WEB_EXT"
	}
	return &Config{
		AuthToken:  mustEnv("SCHNUCKS_AUTH_TOKEN"),
		ClientID:   mustEnv("SCHNUCKS_CLIENT_ID"),
		ClientType: clientType,
		StoreID:    storeID,
		DBPath:     dbPath,
	}
}

// ============================================================================
// API response types
// ============================================================================

type couponResponse struct {
	Data []Coupon `json:"data"`
}

// Coupon represents a Schnucks store coupon or an Ibotta manufacturer rebate.
type Coupon struct {
	ID               int64    `json:"id"`
	Source           string   `json:"source"`
	Description      string   `json:"description"`
	ValueText        string   `json:"valueText"`
	LimitText        string   `json:"limitText"`
	Terms            string   `json:"terms"`
	Category         string   `json:"category"`
	Brand            string   `json:"brand"`
	ImageURL         string   `json:"imageUrl"`
	ExpirationDate   int64    `json:"expirationDate"`
	ClipStartDate    int64    `json:"clipStartDate"`
	ClipEndDate      int64    `json:"clipEndDate"`
	ExpiryType       string   `json:"expiryType"`
	AppOnly          bool     `json:"appOnly"`
	Featured         bool     `json:"featured"`
	FulfillmentType  string   `json:"fulfillmentType"`
	CustomCategories []string `json:"customCategories"`
}

type categoryTreeResponse struct {
	Data Category `json:"data"`
}

// Category represents a node in the Schnucks product category hierarchy.
type Category struct {
	CategoryID      int        `json:"categoryId"`
	Name            string     `json:"name"`
	ImageURL        string     `json:"imageUrl"`
	DisplayOrder    int        `json:"displayOrder"`
	ChildCategories []Category `json:"childCategories"`
	UPCIDs          []int64    `json:"upcIds"`
}

type itemPageResponse struct {
	Data       []Item     `json:"data"`
	Pagination Pagination `json:"pagination"`
}

// Pagination holds page metadata returned by the items endpoint.
type Pagination struct {
	Page       int `json:"page"`
	TotalPages int `json:"totalPages"`
}

// Item represents a Schnucks store product with pricing and coupon linkage.
type Item struct {
	UPCId              int64          `json:"upcId"`
	UPC                string         `json:"upc"`
	FullUPC            string         `json:"fullUpc"`
	Name               string         `json:"name"`
	Description        string         `json:"description"`
	BrandName          string         `json:"brandName"`
	RegularAmount      float64        `json:"regularAmount"`
	AdAmount           *float64       `json:"adAmount"`
	PriceString        string         `json:"priceString"`
	BuyQuantity        *int           `json:"buyQuantity"`
	FreeQuantity       *int           `json:"freeQuantity"`
	Markdown           bool           `json:"markdown"`
	MarkdownPrice      *float64       `json:"markdownPrice"`
	PackageSizeMeasure *float64       `json:"packageSizeMeasure"`
	PackageSizeUOM     string         `json:"packageSizeUom"`
	Aisle              string         `json:"aisle"`
	MainImageURL       string         `json:"mainImageUrl"`
	TaxRate            float64        `json:"taxRate"`
	Location           *ItemLocation  `json:"location"`
	Active             bool           `json:"active"`
	CouponIDs          []int64        `json:"couponIds"`
	CategoryInfoList   []CategoryInfo `json:"categoryInfoList"`
}

// ItemLocation holds the store area label for a product.
type ItemLocation struct {
	Area string `json:"area"`
}

// CategoryInfo is the abbreviated category reference embedded in each item.
type CategoryInfo struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

// ============================================================================
// HTTP client
// ============================================================================

// apiGet performs an authenticated GET against the Schnucks API and decodes
// the JSON response body into dst.
func apiGet(ctx context.Context, client *http.Client, cfg *Config, rawURL string, params url.Values, dst any) error {
	if len(params) > 0 {
		rawURL = rawURL + "?" + params.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, http.NoBody)
	if err != nil {
		return fmt.Errorf("build request for %s: %w", rawURL, err)
	}
	req.Header.Set("authorization", cfg.AuthToken)
	req.Header.Set("x-schnucks-client-type", cfg.ClientType)
	req.Header.Set("x-schnucks-client-id", cfg.ClientID)
	req.Header.Set("content-type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("GET %s: %w", rawURL, err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		snippet, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return fmt.Errorf("HTTP %d from %s: %s", resp.StatusCode, rawURL, snippet)
	}
	if err := json.NewDecoder(resp.Body).Decode(dst); err != nil {
		return fmt.Errorf("decode response from %s: %w", rawURL, err)
	}
	return nil
}

// ============================================================================
// Database schema
// ============================================================================

const schema = `
CREATE TABLE IF NOT EXISTS coupons (
	id                INTEGER PRIMARY KEY,
	source            TEXT    NOT NULL,
	description       TEXT,
	value_text        TEXT,
	limit_text        TEXT,
	terms             TEXT,
	category          TEXT,
	brand             TEXT,
	image_url         TEXT,
	expiration_date   INTEGER,
	clip_start_date   INTEGER,
	clip_end_date     INTEGER,
	expiry_type       TEXT,
	app_only          INTEGER DEFAULT 0,
	featured          INTEGER DEFAULT 0,
	fulfillment_type  TEXT,
	custom_categories TEXT,
	created_at        TEXT    DEFAULT CURRENT_TIMESTAMP,
	updated_at        TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
	upc_id         INTEGER PRIMARY KEY,
	upc            TEXT,
	full_upc       TEXT,
	name           TEXT    NOT NULL,
	description    TEXT,
	brand_name     TEXT,
	regular_price  REAL,
	sale_price     REAL,
	price_string   TEXT,
	buy_quantity   INTEGER,
	free_quantity  INTEGER,
	markdown       INTEGER DEFAULT 0,
	markdown_price REAL,
	size_measure   REAL,
	size_uom       TEXT,
	aisle          TEXT,
	image_url      TEXT,
	tax_rate       REAL,
	area           TEXT,
	active         INTEGER DEFAULT 1,
	created_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
	updated_at     TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS item_coupons (
	upc_id     INTEGER NOT NULL,
	coupon_id  INTEGER NOT NULL,
	created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (upc_id, coupon_id),
	FOREIGN KEY (upc_id)    REFERENCES items(upc_id),
	FOREIGN KEY (coupon_id) REFERENCES coupons(id)
);

CREATE TABLE IF NOT EXISTS categories (
	id            INTEGER PRIMARY KEY,
	name          TEXT    NOT NULL,
	parent_id     INTEGER,
	image_url     TEXT,
	display_order INTEGER,
	is_leaf       INTEGER DEFAULT 0,
	created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS item_categories (
	upc_id      INTEGER NOT NULL,
	category_id INTEGER NOT NULL,
	PRIMARY KEY (upc_id, category_id),
	FOREIGN KEY (upc_id)      REFERENCES items(upc_id),
	FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS scrape_log (
	id            INTEGER PRIMARY KEY AUTOINCREMENT,
	scrape_type   TEXT    NOT NULL,
	category_id   INTEGER,
	items_count   INTEGER,
	coupons_count INTEGER,
	started_at    TEXT,
	completed_at  TEXT,
	status        TEXT,
	error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_coupons_source     ON coupons(source);
CREATE INDEX IF NOT EXISTS idx_coupons_expiration ON coupons(expiration_date);
CREATE INDEX IF NOT EXISTS idx_items_brand        ON items(brand_name);
CREATE INDEX IF NOT EXISTS idx_items_sale         ON items(sale_price) WHERE sale_price IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_item_coupons       ON item_coupons(coupon_id);

CREATE VIEW IF NOT EXISTS v_best_deals AS
SELECT
	i.upc_id,
	i.name,
	i.brand_name,
	i.regular_price,
	i.sale_price,
	COALESCE(i.sale_price, i.regular_price) AS effective_price,
	i.aisle,
	c.source      AS coupon_source,
	c.value_text,
	c.description AS coupon_desc
FROM items i
JOIN item_coupons ic ON i.upc_id    = ic.upc_id
JOIN coupons      c  ON ic.coupon_id = c.id
WHERE c.expiration_date > (strftime('%s', 'now') * 1000)
ORDER BY i.brand_name, i.name;
`

// ============================================================================
// Database helpers
// ============================================================================

// openDB opens the SQLite database at path and applies the schema.
func openDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("open db %s: %w", path, err)
	}
	if _, err := db.Exec(schema); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("apply schema: %w", err)
	}
	return db, nil
}

// closeDB closes the database and logs any error to stderr.
func closeDB(db *sql.DB) {
	if err := db.Close(); err != nil {
		fmt.Fprintf(os.Stderr, "WARNING: close db: %v\n", err)
	}
}

// rollback calls tx.Rollback and discards sql.ErrTxDone, which is expected
// after a successful Commit.
func rollback(tx *sql.Tx) {
	if err := tx.Rollback(); err != nil && !errors.Is(err, sql.ErrTxDone) {
		fmt.Fprintf(os.Stderr, "WARNING: rollback failed: %v\n", err)
	}
}

// boolToInt converts a bool to the SQLite integer representation 0 or 1.
func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

// truncate shortens s to at most n runes, appending "…" when trimmed.
func truncate(s string, n int) string {
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	return string(runes[:n-1]) + "…"
}

// upsertCoupon inserts or updates a single coupon row within a transaction.
func upsertCoupon(tx *sql.Tx, c *Coupon) error {
	cats, err := json.Marshal(c.CustomCategories)
	if err != nil {
		return fmt.Errorf("marshal custom_categories for coupon %d: %w", c.ID, err)
	}
	_, err = tx.Exec(`
		INSERT INTO coupons (
			id, source, description, value_text, limit_text, terms,
			category, brand, image_url, expiration_date, clip_start_date,
			clip_end_date, expiry_type, app_only, featured, fulfillment_type,
			custom_categories, updated_at
		) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
		ON CONFLICT(id) DO UPDATE SET
			source            = excluded.source,
			description       = excluded.description,
			value_text        = excluded.value_text,
			limit_text        = excluded.limit_text,
			terms             = excluded.terms,
			category          = excluded.category,
			brand             = excluded.brand,
			image_url         = excluded.image_url,
			expiration_date   = excluded.expiration_date,
			clip_start_date   = excluded.clip_start_date,
			clip_end_date     = excluded.clip_end_date,
			expiry_type       = excluded.expiry_type,
			app_only          = excluded.app_only,
			featured          = excluded.featured,
			fulfillment_type  = excluded.fulfillment_type,
			custom_categories = excluded.custom_categories,
			updated_at        = CURRENT_TIMESTAMP`,
		c.ID, c.Source, c.Description, c.ValueText, c.LimitText, c.Terms,
		c.Category, c.Brand, c.ImageURL, c.ExpirationDate, c.ClipStartDate,
		c.ClipEndDate, c.ExpiryType, boolToInt(c.AppOnly), boolToInt(c.Featured),
		c.FulfillmentType, string(cats),
	)
	return err
}

// upsertItem inserts or updates an item row and refreshes its coupon and category links.
func upsertItem(tx *sql.Tx, item *Item) error {
	area := ""
	if item.Location != nil {
		area = item.Location.Area
	}
	_, err := tx.Exec(`
		INSERT INTO items (
			upc_id, upc, full_upc, name, description, brand_name,
			regular_price, sale_price, price_string,
			buy_quantity, free_quantity, markdown, markdown_price,
			size_measure, size_uom, aisle, image_url, tax_rate, area, active,
			updated_at
		) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
		ON CONFLICT(upc_id) DO UPDATE SET
			upc            = excluded.upc,
			full_upc       = excluded.full_upc,
			name           = excluded.name,
			description    = excluded.description,
			brand_name     = excluded.brand_name,
			regular_price  = excluded.regular_price,
			sale_price     = excluded.sale_price,
			price_string   = excluded.price_string,
			buy_quantity   = excluded.buy_quantity,
			free_quantity  = excluded.free_quantity,
			markdown       = excluded.markdown,
			markdown_price = excluded.markdown_price,
			size_measure   = excluded.size_measure,
			size_uom       = excluded.size_uom,
			aisle          = excluded.aisle,
			image_url      = excluded.image_url,
			tax_rate       = excluded.tax_rate,
			area           = excluded.area,
			active         = excluded.active,
			updated_at     = CURRENT_TIMESTAMP`,
		item.UPCId, item.UPC, item.FullUPC, item.Name, item.Description, item.BrandName,
		item.RegularAmount, item.AdAmount, item.PriceString,
		item.BuyQuantity, item.FreeQuantity, boolToInt(item.Markdown), item.MarkdownPrice,
		item.PackageSizeMeasure, item.PackageSizeUOM, item.Aisle, item.MainImageURL,
		item.TaxRate, area, boolToInt(item.Active),
	)
	if err != nil {
		return fmt.Errorf("upsert item %d: %w", item.UPCId, err)
	}

	if _, err := tx.Exec("DELETE FROM item_coupons WHERE upc_id = ?", item.UPCId); err != nil {
		return fmt.Errorf("clear coupon links for item %d: %w", item.UPCId, err)
	}
	for _, cid := range item.CouponIDs {
		if _, err := tx.Exec(
			"INSERT OR IGNORE INTO item_coupons (upc_id, coupon_id) VALUES (?,?)",
			item.UPCId, cid,
		); err != nil {
			return fmt.Errorf("link coupon %d to item %d: %w", cid, item.UPCId, err)
		}
	}

	if _, err := tx.Exec("DELETE FROM item_categories WHERE upc_id = ?", item.UPCId); err != nil {
		return fmt.Errorf("clear category links for item %d: %w", item.UPCId, err)
	}
	for _, cat := range item.CategoryInfoList {
		if _, err := tx.Exec(
			"INSERT OR IGNORE INTO item_categories (upc_id, category_id) VALUES (?,?)",
			item.UPCId, cat.ID,
		); err != nil {
			return fmt.Errorf("link category %d to item %d: %w", cat.ID, item.UPCId, err)
		}
	}
	return nil
}

// upsertCategory recursively inserts or updates a category node and all descendants.
func upsertCategory(tx *sql.Tx, cat *Category, parentID *int) error {
	isLeaf := boolToInt(len(cat.UPCIDs) > 0 || len(cat.ChildCategories) == 0)
	_, err := tx.Exec(`
		INSERT INTO categories (id, name, parent_id, image_url, display_order, is_leaf)
		VALUES (?,?,?,?,?,?)
		ON CONFLICT(id) DO UPDATE SET
			name          = excluded.name,
			parent_id     = excluded.parent_id,
			image_url     = excluded.image_url,
			display_order = excluded.display_order,
			is_leaf       = excluded.is_leaf`,
		cat.CategoryID, cat.Name, parentID, cat.ImageURL, cat.DisplayOrder, isLeaf,
	)
	if err != nil {
		return fmt.Errorf("upsert category %d: %w", cat.CategoryID, err)
	}
	for i := range cat.ChildCategories {
		id := cat.CategoryID
		if err := upsertCategory(tx, &cat.ChildCategories[i], &id); err != nil {
			return err
		}
	}
	return nil
}

// ============================================================================
// API fetchers
// ============================================================================

// fetchCoupons retrieves all coupons from the Schnucks API.
func fetchCoupons(ctx context.Context, client *http.Client, cfg *Config) ([]Coupon, error) {
	var resp couponResponse
	if err := apiGet(ctx, client, cfg, baseURL+"/coupon-api/v1/coupons", nil, &resp); err != nil {
		return nil, fmt.Errorf("fetch coupons: %w", err)
	}
	return resp.Data, nil
}

// fetchCategoryTree retrieves the full product category hierarchy.
func fetchCategoryTree(ctx context.Context, client *http.Client, cfg *Config) (Category, error) {
	var resp categoryTreeResponse
	params := url.Values{"store": {cfg.StoreID}}
	if err := apiGet(ctx, client, cfg, baseURL+"/item-catalog-api/v1/category-trees/HOME_SHOP", params, &resp); err != nil {
		return Category{}, fmt.Errorf("fetch category tree: %w", err)
	}
	return resp.Data, nil
}

// fetchAllItemsInCategory paginates through all items in a category.
func fetchAllItemsInCategory(ctx context.Context, client *http.Client, cfg *Config, categoryID int) ([]Item, error) {
	var all []Item
	for page := 0; ; page++ {
		params := url.Values{
			"store":           {cfg.StoreID},
			"fulfillmentType": {"SELF"},
			"page":            {strconv.Itoa(page)},
			"size":            {strconv.Itoa(pageSize)},
		}
		rawURL := fmt.Sprintf("%s/item-catalog-api/v1/categories/%d/items", baseURL, categoryID)

		var resp itemPageResponse
		if err := apiGet(ctx, client, cfg, rawURL, params, &resp); err != nil {
			return nil, fmt.Errorf("fetch items page %d for category %d: %w", page, categoryID, err)
		}
		all = append(all, resp.Data...)
		if page >= resp.Pagination.TotalPages-1 || len(resp.Data) == 0 {
			break
		}
		time.Sleep(requestDelay)
	}
	return all, nil
}

// ============================================================================
// Commands
// ============================================================================

// cmdInit initializes the database schema without scraping.
func cmdInit(cfg *Config) error {
	db, err := openDB(cfg.DBPath)
	if err != nil {
		return err
	}
	closeDB(db)
	fmt.Printf("Database initialized: %s\n", cfg.DBPath)
	return nil
}

// cmdCoupons scrapes and stores all coupons.
func cmdCoupons(ctx context.Context, client *http.Client, cfg *Config) error {
	db, err := openDB(cfg.DBPath)
	if err != nil {
		return err
	}
	defer closeDB(db)

	fmt.Println("Fetching coupons...")
	coupons, err := fetchCoupons(ctx, client, cfg)
	if err != nil {
		return err
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin transaction: %w", err)
	}
	defer rollback(tx)

	for i := range coupons {
		if err := upsertCoupon(tx, &coupons[i]); err != nil {
			return err
		}
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("commit coupons: %w", err)
	}

	s, ib := countBySource(coupons)
	fmt.Printf("  Stored %d coupons (%d Schnucks + %d Ibotta)\n", len(coupons), s, ib)
	return nil
}

// cmdCategories scrapes and stores the full category tree.
func cmdCategories(ctx context.Context, client *http.Client, cfg *Config) error {
	db, err := openDB(cfg.DBPath)
	if err != nil {
		return err
	}
	defer closeDB(db)

	fmt.Println("Fetching category tree...")
	tree, err := fetchCategoryTree(ctx, client, cfg)
	if err != nil {
		return err
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin transaction: %w", err)
	}
	defer rollback(tx)

	if err := upsertCategory(tx, &tree, nil); err != nil {
		return err
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("commit categories: %w", err)
	}

	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM categories").Scan(&count); err != nil {
		return fmt.Errorf("count categories: %w", err)
	}
	fmt.Printf("  Stored %d categories\n", count)
	return nil
}

// cmdItems scrapes all items from every leaf category.
func cmdItems(ctx context.Context, client *http.Client, cfg *Config) error {
	db, err := openDB(cfg.DBPath)
	if err != nil {
		return err
	}
	defer closeDB(db)

	rows, err := db.QueryContext(ctx, "SELECT id, name FROM categories WHERE is_leaf = 1")
	if err != nil {
		return fmt.Errorf("query leaf categories: %w", err)
	}
	defer func() { _ = rows.Close() }()

	type catRow struct {
		ID   int
		Name string
	}
	var cats []catRow
	for rows.Next() {
		var r catRow
		if err := rows.Scan(&r.ID, &r.Name); err != nil {
			return fmt.Errorf("scan category row: %w", err)
		}
		cats = append(cats, r)
	}
	if err := rows.Err(); err != nil {
		return fmt.Errorf("iterate categories: %w", err)
	}

	fmt.Printf("Scraping %d categories...\n", len(cats))
	total := 0
	for i, cat := range cats {
		fmt.Printf("  [%d/%d] %s (%d)... ", i+1, len(cats), cat.Name, cat.ID)

		items, err := fetchAllItemsInCategory(ctx, client, cfg, cat.ID)
		if err != nil {
			fmt.Printf("ERROR: %v\n", err)
			continue
		}

		tx, err := db.BeginTx(ctx, nil)
		if err != nil {
			return fmt.Errorf("begin transaction for category %d: %w", cat.ID, err)
		}
		for j := range items {
			if err := upsertItem(tx, &items[j]); err != nil {
				rollback(tx)
				return err
			}
		}
		if err := tx.Commit(); err != nil {
			return fmt.Errorf("commit items for category %d: %w", cat.ID, err)
		}

		fmt.Printf("%d items\n", len(items))
		total += len(items)
		time.Sleep(requestDelay)
	}

	fmt.Printf("Total items scraped: %d\n", total)
	return nil
}

// cmdFull runs a complete scrape: coupons → categories → items.
func cmdFull(ctx context.Context, client *http.Client, cfg *Config) error {
	started := time.Now()
	sep := strings.Repeat("=", 60)
	fmt.Printf("%s\nSCHNUCKS FULL SCRAPE\n%s\n", sep, sep)

	if err := cmdCoupons(ctx, client, cfg); err != nil {
		return fmt.Errorf("coupons stage: %w", err)
	}
	if err := cmdCategories(ctx, client, cfg); err != nil {
		return fmt.Errorf("categories stage: %w", err)
	}
	if err := cmdItems(ctx, client, cfg); err != nil {
		return fmt.Errorf("items stage: %w", err)
	}

	fmt.Printf("%s\nCOMPLETE in %s\n%s\n", sep, time.Since(started).Round(time.Second), sep)
	return nil
}

// cmdStats prints current database statistics.
func cmdStats(cfg *Config) error {
	db, err := sql.Open("sqlite", cfg.DBPath)
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer closeDB(db)

	var (
		coupons, schnucks, ibotta int
		items, links, cats        int
		itemsWithCoupons, onSale  int
	)
	for _, q := range []struct {
		dest  *int
		query string
	}{
		{&coupons, "SELECT COUNT(*) FROM coupons"},
		{&schnucks, "SELECT COUNT(*) FROM coupons WHERE source='SCHNUCKS'"},
		{&ibotta, "SELECT COUNT(*) FROM coupons WHERE source='IBOTTA'"},
		{&items, "SELECT COUNT(*) FROM items"},
		{&links, "SELECT COUNT(*) FROM item_coupons"},
		{&cats, "SELECT COUNT(*) FROM categories"},
		{&itemsWithCoupons, "SELECT COUNT(DISTINCT upc_id) FROM item_coupons"},
		{&onSale, "SELECT COUNT(*) FROM items WHERE sale_price IS NOT NULL"},
	} {
		if err := db.QueryRow(q.query).Scan(q.dest); err != nil {
			return fmt.Errorf("stat query %q: %w", q.query, err)
		}
	}

	fmt.Printf(
		"Schnucks Deal Database\n======================\n"+
			"Coupons:    %d total (%d Schnucks + %d Ibotta)\n"+
			"Items:      %d products\n"+
			"Links:      %d item-coupon links\n"+
			"Categories: %d\n\n"+
			"Items with coupons: %d\n"+
			"Items on sale:      %d\n",
		coupons, schnucks, ibotta, items, links, cats, itemsWithCoupons, onSale,
	)
	return nil
}

// cmdDeals prints the top 50 items with active coupons.
func cmdDeals(cfg *Config) error {
	db, err := sql.Open("sqlite", cfg.DBPath)
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer closeDB(db)

	rows, err := db.Query(`
		SELECT i.brand_name, i.name, i.regular_price, c.value_text
		FROM items i
		JOIN item_coupons ic ON i.upc_id    = ic.upc_id
		JOIN coupons      c  ON ic.coupon_id = c.id
		WHERE c.expiration_date > (strftime('%s','now') * 1000)
		ORDER BY i.brand_name, i.name
		LIMIT 50`)
	if err != nil {
		return fmt.Errorf("query deals: %w", err)
	}
	defer func() { _ = rows.Close() }()

	for rows.Next() {
		var brand, name, valueText string
		var price float64
		if err := rows.Scan(&brand, &name, &price, &valueText); err != nil {
			return fmt.Errorf("scan deal row: %w", err)
		}
		fmt.Printf("%-20s %-45s $%5.2f  %s\n", truncate(brand, 20), truncate(name, 45), price, valueText)
	}
	return rows.Err()
}

// ============================================================================
// Utilities
// ============================================================================

// countBySource tallies coupons into Schnucks and Ibotta buckets.
func countBySource(coupons []Coupon) (schnucks, ibotta int) {
	for i := range coupons {
		switch coupons[i].Source {
		case "SCHNUCKS":
			schnucks++
		case "IBOTTA":
			ibotta++
		}
	}
	return schnucks, ibotta
}

// ============================================================================
// Entry point
// ============================================================================

const usage = `Usage: harvester <command>

Commands:
  init        Initialize database schema
  coupons     Scrape coupons only
  categories  Scrape category tree
  items       Scrape all items (requires categories)
  full        Full scrape: coupons + categories + items
  stats       Show database statistics
  deals       Show items with active coupons`

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, usage)
		os.Exit(1)
	}

	exe, err := os.Executable()
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: resolve executable path: %v\n", err)
		os.Exit(1)
	}
	dir := filepath.Dir(exe)

	envPath := filepath.Join(dir, ".env")
	dbPath := filepath.Join(dir, "..", "data", "schnucks.db")

	if err := loadEnv(envPath); err != nil && !os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "WARNING: could not load .env: %v\n", err)
	}

	cfg := loadConfig(dbPath)
	client := &http.Client{Timeout: httpTimeout}
	ctx := context.Background()

	var runErr error
	switch strings.ToLower(os.Args[1]) {
	case "init":
		runErr = cmdInit(cfg)
	case "coupons":
		runErr = cmdCoupons(ctx, client, cfg)
	case "categories":
		runErr = cmdCategories(ctx, client, cfg)
	case "items":
		runErr = cmdItems(ctx, client, cfg)
	case "full":
		runErr = cmdFull(ctx, client, cfg)
	case "stats":
		runErr = cmdStats(cfg)
	case "deals":
		runErr = cmdDeals(cfg)
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n\n%s\n", os.Args[1], usage)
		os.Exit(1)
	}

	if runErr != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", runErr)
		os.Exit(1)
	}
}
