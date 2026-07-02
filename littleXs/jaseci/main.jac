"""Little X - Headless backend entry for the DBHarness benchmark server.

No frontend. Importing the app walkers here brings them into the served module
so jac-cloud exposes each as `POST /walker/<name>`. The `import_data` seed
walker lives in a separate module (`import_data.jac`) — uncomment its import
once that file exists.
"""

import from app {
    setup_profile,
    get_profile,
    get_profile_by_id,
    load_feed,
    create_tweet
}

# import from import_data { import_data }   # <- uncomment when import_data.jac is written
