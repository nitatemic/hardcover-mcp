"""
All GraphQL queries and mutations used by the Hardcover MCP server.

Each constant is a ready-to-use query string.  Variables are passed
separately so the client can serialize them correctly.

Important: a single request may contain at most 5 top-level queries.
Every query here is intentionally one top-level field.

Status IDs (user_books.status_id):
    1 = Want to Read
    2 = Currently Reading
    3 = Read
    4 = Paused
    5 = Did Not Finish
    6 = Ignored
"""

# ---------------------------------------------------------------------------
# Me / current user
# ---------------------------------------------------------------------------

ME = """
query Me {
  me {
    id
    username
    name
    reading_journal_entries_count
    user_books_count
  }
}
"""

# ---------------------------------------------------------------------------
# Search  (counts as 1 request; max 1 search per top-level)
# ---------------------------------------------------------------------------

SEARCH = """
query Search(
  $query: String!
  $query_type: String
  $per_page: Int
  $page: Int
) {
  search(
    query: $query
    query_type: $query_type
    per_page: $per_page
    page: $page
  ) {
    results
    query
    query_type
    page
    per_page
  }
}
"""

# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------

GET_BOOK_BY_ID = """
query GetBookById($id: Int!) {
  books(where: {id: {_eq: $id}}) {
    id
    title
    subtitle
    slug
    description
    release_date
    pages
    rating
    ratings_count
    users_count
    users_read_count
    image {
      url
    }
    contributions {
      author {
        id
        name
        slug
      }
    }
    book_series {
      position
      series {
        id
        name
        slug
      }
    }
  }
}
"""

GET_BOOK_BY_SLUG = """
query GetBookBySlug($slug: String!) {
  books(where: {slug: {_eq: $slug}}) {
    id
    title
    subtitle
    slug
    description
    release_date
    pages
    rating
    ratings_count
    users_count
    users_read_count
    image {
      url
    }
    contributions {
      author {
        id
        name
        slug
      }
    }
    book_series {
      position
      series {
        id
        name
        slug
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Editions
# ---------------------------------------------------------------------------

GET_EDITIONS_BY_TITLE = """
query GetEditionsByTitle($title: String!) {
  editions(where: {title: {_eq: $title}}) {
    id
    title
    edition_format
    pages
    release_date
    isbn_10
    isbn_13
    publisher {
      name
    }
    book {
      id
      title
      slug
    }
  }
}
"""

GET_EDITION_BY_ID = """
query GetEditionById($id: Int!) {
  editions(where: {id: {_eq: $id}}) {
    id
    title
    edition_format
    pages
    release_date
    isbn_10
    isbn_13
    publisher {
      name
    }
    book {
      id
      title
      subtitle
      slug
      release_date
      contributions {
        author {
          name
        }
      }
    }
  }
}
"""

GET_EDITIONS_BY_ISBN = """
query GetEditionsByIsbn($isbn: String!) {
  editions(where: {_or: [{isbn_10: {_eq: $isbn}}, {isbn_13: {_eq: $isbn}}]}) {
    id
    title
    edition_format
    pages
    release_date
    isbn_10
    isbn_13
    publisher {
      name
    }
    book {
      id
      title
      slug
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

GET_AUTHOR_BY_ID = """
query GetAuthorById($id: Int!) {
  authors(where: {id: {_eq: $id}}) {
    id
    name
    slug
    bio
    image {
      url
    }
    books_count
  }
}
"""

GET_AUTHOR_BY_SLUG = """
query GetAuthorBySlug($slug: String!) {
  authors(where: {slug: {_eq: $slug}}) {
    id
    name
    slug
    bio
    image {
      url
    }
    books_count
  }
}
"""

GET_AUTHOR_BOOKS = """
query GetAuthorBooks($author_id: Int!, $limit: Int, $offset: Int) {
  books(
    where: {
      contributions: {
        author_id: {_eq: $author_id}
      }
      canonical_id: {_is_null: true}
    }
    order_by: {users_count: desc}
    limit: $limit
    offset: $offset
  ) {
    id
    title
    subtitle
    slug
    release_date
    pages
    rating
    ratings_count
    users_count
    image {
      url
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------

GET_SERIES_BY_ID = """
query GetSeriesById($id: Int!) {
  series(where: {id: {_eq: $id}}) {
    id
    name
    slug
    description
    books_count
  }
}
"""

GET_BOOKS_IN_SERIES = """
query GetBooksInSeries($series_id: Int!) {
  book_series(
    where: {
      series_id: {_eq: $series_id}
      book: {
        canonical_id: {_is_null: true}
        is_partial_book: {_eq: false}
      }
      compilation: {_eq: false}
    }
    distinct_on: position
    order_by: [
      {position: asc}
      {book: {users_count: desc}}
    ]
  ) {
    position
    details
    book {
      id
      title
      slug
      release_date
      pages
      image {
        url
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# User library
# ---------------------------------------------------------------------------

GET_MY_LIBRARY = """
query GetMyLibrary($limit: Int, $offset: Int) {
  me {
    user_books(
      distinct_on: book_id
      limit: $limit
      offset: $offset
    ) {
      status_id
      rating
      book {
        id
        title
        slug
        pages
        release_date
        image {
          url
        }
        contributions {
          author {
            name
          }
        }
      }
    }
  }
}
"""

GET_LIBRARY_BY_STATUS = """
query GetLibraryByStatus($status_id: Int!, $limit: Int, $offset: Int) {
  me {
    user_books(
      where: {status_id: {_eq: $status_id}}
      limit: $limit
      offset: $offset
    ) {
      status_id
      rating
      book {
        id
        title
        slug
        pages
        release_date
        image {
          url
        }
        contributions {
          author {
            name
          }
        }
      }
    }
  }
}
"""

GET_READING_PROGRESS = """
query GetReadingProgress {
  me {
    id
    user_books(where: {status_id: {_eq: 2}}) {
      id
      user_book_reads {
        progress_pages
        progress_seconds
        started_at
        finished_at
      }
      book {
        id
        title
        slug
        pages
        image {
          url
        }
      }
    }
  }
}
"""

GET_USER_BOOK = """
query GetUserBook($book_id: Int!) {
  me {
    user_books(where: {book_id: {_eq: $book_id}}) {
      id
      status_id
      rating
      review
      user_book_reads {
        id
        progress_pages
        progress_seconds
        started_at
        finished_at
        edition {
          id
          title
          edition_format
        }
      }
      book {
        id
        title
        slug
        pages
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# User profile (by username)
# ---------------------------------------------------------------------------

GET_USER_LIBRARY_BY_STATUS = """
query GetUserLibraryByStatus(
  $user_id: Int!
  $status_id: Int!
  $limit: Int
  $offset: Int
) {
  user_books(
    where: {
      user_id: {_eq: $user_id}
      status_id: {_eq: $status_id}
    }
    limit: $limit
    offset: $offset
    distinct_on: book_id
  ) {
    book {
      id
      title
      slug
      pages
      release_date
      image {
        url
      }
      contributions {
        author {
          name
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Reading journals
# ---------------------------------------------------------------------------

GET_MY_READING_JOURNAL = """
query GetMyReadingJournal($book_id: Int!) {
  me {
    user_books(where: {book_id: {_eq: $book_id}}) {
      id
      status_id
      rating
      user_book_reads {
        id
        started_at
        finished_at
        progress_pages
        edition {
          id
          title
          edition_format
        }
      }
    }
  }
  reading_journals(
    where: {book_id: {_eq: $book_id}}
    order_by: {action_at: desc}
  ) {
    id
    event
    entry
    action_at
    created_at
    metadata
    edition_id
  }
}
"""

# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

GET_LIST_BY_ID = """
query GetListById($id: Int!) {
  lists(where: {id: {_eq: $id}}) {
    id
    name
    description
    slug
    books_count
    user {
      username
    }
    list_books(order_by: {position: asc}, limit: 50) {
      position
      book {
        id
        title
        slug
        image {
          url
        }
        contributions {
          author {
            name
          }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Reading stats  (user_books_aggregate)
# ---------------------------------------------------------------------------

GET_READING_STATS = """
query GetReadingStats($user_id: Int!, $since: date) {
  all_time: user_books_aggregate(
    where: {
      user_id: {_eq: $user_id}
      status_id: {_eq: 3}
    }
  ) {
    aggregate {
      count
      avg { rating }
    }
  }
  filtered: user_books_aggregate(
    where: {
      user_id: {_eq: $user_id}
      status_id: {_eq: 3}
      last_read_date: {_gte: $since}
    }
  ) {
    aggregate {
      count
      avg { rating }
    }
  }
}
"""

# Fetch books read in a date range (list form, with dates)
GET_BOOKS_READ_BETWEEN = """
query GetBooksReadBetween(
  $user_id: Int!
  $since: date!
  $until: date!
  $limit: Int
  $offset: Int
) {
  user_books(
    where: {
      user_id: {_eq: $user_id}
      status_id: {_eq: 3}
      last_read_date: {_gte: $since, _lte: $until}
    }
    order_by: {last_read_date: desc}
    limit: $limit
    offset: $offset
  ) {
    last_read_date
    first_read_date
    rating
    book {
      id
      title
      slug
      pages
      image { url }
      contributions {
        author { name }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

GET_MY_GOALS = """
query GetMyGoals {
  me {
    goals(order_by: {start_date: desc}) {
      id
      description
      goal
      metric
      progress
      state
      start_date
      end_date
      completed_at
      privacy_setting_id
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

GET_MY_ACTIVITIES = """
query GetMyActivities($user_id: Int!, $limit: Int, $offset: Int) {
  activities(
    where: {user_id: {_eq: $user_id}}
    order_by: {created_at: desc}
    limit: $limit
    offset: $offset
  ) {
    id
    event
    created_at
    book_id
    likes_count
    data
    book {
      id
      title
      slug
      image { url }
    }
  }
}
"""

GET_BOOK_ACTIVITIES = """
query GetBookActivities($book_id: Int!, $limit: Int, $offset: Int) {
  activities(
    where: {
      book_id: {_eq: $book_id}
      event: {_eq: "UserBookActivity"}
    }
    order_by: {created_at: desc}
    limit: $limit
    offset: $offset
  ) {
    id
    event
    created_at
    likes_count
    data
    user {
      id
      username
      name
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Updated ME query with full fields
# ---------------------------------------------------------------------------

ME_FULL = """
query Me {
  me {
    id
    username
    name
    bio
    location
    flair
    pro
    books_count
    followers_count
    followed_users_count
    cached_image
  }
}
"""
