# SQL Scripts
These SQL scripts allow you to monitor and analyze how users and groups are interacting with your bot.

## Count the total number of feeds each user or group is subscribed to
```sql
SELECT user_id AS "User/Group", COUNT(id) AS "Number of feeds"
FROM sub
GROUP BY user_id
ORDER BY COUNT(id) DESC;
```

## List each user/group with the titles and links of their subscribed feeds
```sql
SELECT 
  s.user_id AS "User/Group", 
  GROUP_CONCAT(f.title, CHAR(10)) AS "Feed Title",
  GROUP_CONCAT(f.link, CHAR(10)) AS "Feed Link",
  COUNT(*) AS feed_count
FROM sub s
JOIN feed f ON s.feed_id = f.id
GROUP BY s.user_id
ORDER BY feed_count DESC;
```
