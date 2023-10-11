# rdm
Arches Reference Data Manager Application

##### Setup
1.
    a. if working locally, run `pip install .` inside arches application to copy files into ENV or `pip install -e .` to create an egg link to a local arches application.
    b. if not working locally run `pip install arches-rdm`
2.  ( optional ) create a project
```
arches-project create $PROJECT_NAME
```
3. add package to INSTALLED_APPS and ARCHES_APPLICATIONS
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
4. add arches_applications to dependencies in package.json
```
"dependencies": {
 "arches": "archesproject/arches#stable/7.4.0",
 "arches_rdm": "archesproject/arches-rdm"
}
```
5. Install arches_application dependencies
```
yarn install
```
6.
```
urlpatterns = [
    url(r'^', include('arches.urls')),
    url(r"^", include("arches_rdm.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```
