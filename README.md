# Lingo
Lingo Application (Vocabulary Management)

##### Setup
1.
    a. if working locally, run `pip install .` inside arches application to copy files into ENV or `pip install -e .` to create an egg link to a local arches application.
    b. if not working locally run `pip install arches-rdm`
2.  Create a project if not installing into already-existing project.
```
arches-project create $PROJECT_NAME
```
3. Add package to INSTALLED_APPS and ARCHES_APPLICATIONS
```
INSTALLED_APPS = (
    ...,
    "arches_rdm"
)
ARCHES_APPLICATIONS = (
    ...,
    'arches_rdm',
)
```
4. Add arches_applications to dependencies in package.json
```
"dependencies": {
    "arches": "archesproject/arches#dev/7.6.x",
    "arches_rdm": "archesproject/arches-rdm"
}
```
5. Install arches_application dependencies
```
yarn install
```
6. Add the application urls to the project's `urls.py`
```
urlpatterns = [
    path('', include('arches.urls')),
    path('', include("arches_rdm.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

7. This project currently uses a frontend outside of Arches. To allow it to communicate with Django, add this to your project `settings.py`:

```
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGIN_ALLOW_ALL = False
CORS_ORIGIN_WHITELIST = ["http://localhost:8080"]  # vue frontend
CSRF_TRUSTED_ORIGINS = ["http://localhost:8080"]  # vue frontend
```

NOTE: This rough draft currently assumes the Django backend is served at `https://127.0.0.1:8029/`.

Run the frontend with:
```
npm run serve
```
