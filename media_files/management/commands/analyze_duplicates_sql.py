"""SQL queries to analyze duplicate VideoFile records.

This file contains SQL queries that can be run directly in database
to quickly find and analyze duplicate VideoFile records by number.
"""

# Query 1: Find all numbers with duplicates
FIND_DUPLICATES = """
SELECT number, COUNT(*) as count
FROM media_files_videofile
GROUP BY number
HAVING COUNT(*) > 1
ORDER BY count DESC, number;
"""

# Query 2: Detailed view of duplicates with key differences
DETAILED_DUPLICATES = """
SELECT 
    v1.number,
    v1.id as id1,
    v1.file_path as path1,
    v1.file_size as size1,
    v1.checksum as checksum1,
    v1.duration as duration1,
    v1.created_at as created1,
    v1.updated_at as updated1,
    v1.is_available as available1,
    v1.license_id as license_id1,
    sl1.name as storage1,
    v2.id as id2,
    v2.file_path as path2,
    v2.file_size as size2,
    v2.checksum as checksum2,
    v2.duration as duration2,
    v2.created_at as created2,
    v2.updated_at as updated2,
    v2.is_available as available2,
    v2.license_id as license_id2,
    sl2.name as storage2,
    CASE 
        WHEN v1.checksum = v2.checksum AND v1.checksum IS NOT NULL THEN 'IDENTICAL'
        WHEN v1.checksum != v2.checksum AND v1.checksum IS NOT NULL AND v2.checksum IS NOT NULL THEN 'DIFFERENT'
        ELSE 'UNKNOWN'
    END as checksum_match
FROM media_files_videofile v1
JOIN media_files_videofile v2 ON v1.number = v2.number AND v1.id < v2.id
LEFT JOIN media_files_storagelocation sl1 ON v1.storage_location_id = sl1.id
LEFT JOIN media_files_storagelocation sl2 ON v2.storage_location_id = sl2.id
ORDER BY v1.number, v1.id;
"""

# Query 3: Count duplicates by storage location
DUPLICATES_BY_STORAGE = """
SELECT 
    sl.name as storage_name,
    sl.storage_type,
    COUNT(DISTINCT v.number) as numbers_with_duplicates,
    COUNT(*) - COUNT(DISTINCT v.number) as total_duplicate_files
FROM media_files_videofile v
JOIN media_files_storagelocation sl ON v.storage_location_id = sl.id
WHERE v.number IN (
    SELECT number 
    FROM media_files_videofile 
    GROUP BY number 
    HAVING COUNT(*) > 1
)
GROUP BY sl.id, sl.name, sl.storage_type
ORDER BY total_duplicate_files DESC;
"""

# Query 4: Find duplicates with same checksum (safe to delete)
IDENTICAL_DUPLICATES = """
SELECT 
    v1.number,
    v1.id as id1,
    v1.file_path as path1,
    v1.created_at as created1,
    sl1.name as storage1,
    v2.id as id2,
    v2.file_path as path2,
    v2.created_at as created2,
    sl2.name as storage2
FROM media_files_videofile v1
JOIN media_files_videofile v2 ON v1.number = v2.number AND v1.id < v2.id
LEFT JOIN media_files_storagelocation sl1 ON v1.storage_location_id = sl1.id
LEFT JOIN media_files_storagelocation sl2 ON v2.storage_location_id = sl2.id
WHERE v1.checksum = v2.checksum 
  AND v1.checksum IS NOT NULL 
  AND v1.checksum != ''
ORDER BY v1.number, v1.id;
"""

# Query 5: Find duplicates linked to different licenses (data inconsistency)
DUPLICATES_DIFFERENT_LICENSES = """
SELECT 
    v1.number,
    v1.id as id1,
    v1.license_id as license_id1,
    v2.id as id2,
    v2.license_id as license_id2
FROM media_files_videofile v1
JOIN media_files_videofile v2 ON v1.number = v2.number AND v1.id < v2.id
WHERE v1.license_id IS NOT NULL 
  AND v2.license_id IS NOT NULL 
  AND v1.license_id != v2.license_id
ORDER BY v1.number;
"""

if __name__ == '__main__':
    print("SQL Queries for Analyzing VideoFile Duplicates")
    print("=" * 60)
    print("\n1. Find all numbers with duplicates:")
    print(FIND_DUPLICATES)
    print("\n2. Detailed view of duplicates:")
    print(DETAILED_DUPLICATES)
    print("\n3. Count duplicates by storage location:")
    print(DUPLICATES_BY_STORAGE)
    print("\n4. Find identical duplicates (same checksum - safe to delete):")
    print(IDENTICAL_DUPLICATES)
    print("\n5. Find duplicates linked to different licenses:")
    print(DUPLICATES_DIFFERENT_LICENSES)
