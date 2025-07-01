<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link
      rel="icon"
      type="image/png"
      sizes="32x32"
      href="${request.static_url('/app/shared_config_manager/static/favicon-32x32.png')}"
      referrerpolicy="no-referrer"
    />
    <link
      rel="icon"
      type="image/png"
      sizes="16x16"
      href="${request.static_url('/app/shared_config_manager/static/favicon-16x16.png')}"
      referrerpolicy="no-referrer"
    />
    <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.7/css/bootstrap.min.css"
        integrity="sha512-fw7f+TcMjTb7bpbLJZlP8g2Y4XcCyFZW8uy8HsRZsH/SwbMw0plKHFHr99DN3l04VsYNwvzicUX/6qurvIxbxw=="
        crossorigin="anonymous"
        referrerpolicy="no-referrer"
    />
    <title>Shared config manager</title>
  </head>
  <body style="padding-bottom: 1rem;">
    <script>
      (() => {
        'use strict'
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
          document.documentElement.setAttribute('data-bs-theme', 'dark');
        }
      })()
    </script>
    <div class="container-fluid">
      <h1>Shared config manager</h1>

      <p style="text-align: right;">
      %if request.identity is not None:
      Logged as: <a href="${request.identity.url}">${request.identity.name}</a>,
      <a role="button" class="btn btn-secondary mt-4"
      href="${request.route_url('c2c_github_logout', _query={'came_from': request.current_route_url()})}" style="vertical-align: baseline;">Logout</a>
      %else:
      <a class="btn btn-primary"
      href="${request.route_url('c2c_github_login', _query={'came_from': request.current_route_url()})}">Login with GitHub</a>
      %endif
      </p>

      %if sources:
      <h3>Sources</h3>
      <ul class="list-group">
        %for source in sources:
        <li class="list-group-item">
          %if is_valid(source):
          <span class="badge bg-success">✓</span>
          %else:
          <span class="badge bg-danger">✗</span>
          %endif
          <a href="${request.route_url('ui_source', id=source.get_id())}"
            >${source.get_config().get("name", source.get_id()) | h}</a>
        </li>
        %endfor
      </ul>
      %endif
    </div>
  </body>
</html>
