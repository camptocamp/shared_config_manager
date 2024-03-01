<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
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
        href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.3/css/bootstrap.min.css"
        integrity="sha512-jnSuA4Ss2PkkikSOLtYs8BlYIeeIK1h99ty4YfvRPAlzr377vr3CXDb7sb7eEEBYjDtcYj+AjBH3FLv5uSJuXg=="
        crossorigin="anonymous"
        referrerpolicy="no-referrer"
    />
    <link rel="stylesheet" href="style.css" />
    <title>Shared config manager - ${source.get_config().get("name", source.get_id()) | h}</title>
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
      <div style="position: absolute; right: 1rem;">
        <p style="text-align: right;">
         %if request.identity is not None:
         Logged as: <a href="${request.identity.url}">${request.identity.name}</a>,
         <a role="button" class="btn btn-secondary mt-4"
         href="${request.route_url('c2c_github_logout', _query={'came_from': request.current_route_url()}) | h}" style="vertical-align: baseline;">Logout</a>
         %else:
         <a class="btn btn-primary"
         href="${request.route_url('c2c_github_login', _query={'came_from': request.current_route_url()}) | h}">Login with GitHub</a>
         %endif
        </p>

        <p style="text-align: right;">
          <a class="btn btn-secondary" href="${request.route_url('ui_index') | h}">Back to the list</a>
          <a class="btn btn-secondary" target="_blank" href="${request.route_url('refresh', id=source.get_id()) | h}">Refresh</a>
        </p>
      </div>

      <h1 style="margin-bottom: 4rem;">${source.get_config().get("name", source.get_id()) | h}</h1>

      <h3>Config</h3>
      <dl class="border rounded row mx-1">
        %for c1, c2, c3, c4 in attributes:
        <dt class="col-lg-2">${c1 | h}</dt>
        <dd class="col-lg-4">${c2 | h}</dd>
        <dt class="col-lg-2">${c3 | h}</dt>
        <dd class="col-lg-4">${c4 | h}</dd>
        %endfor
      </dl>

      %if slave_status:
      <h3>Slaves statuses</h3>
      <ul class="list-group">
        %for status, commit in slave_status:
        <li class="list-group-item">
        <div class="row align-items-start">
          <div class="col">
            <h4>${status.get('hostname') | h}</h4>
            <p>
            Tags: ${', '.join(status.get('tags', [])) if status.get('tags', []) else '-' | h}<br>
            %if commit:
              %for s in commit:
              <br />
              %if isinstance(s, tuple):
              <a href="${s[0]}">${s[1]}</a>
              %else:
              ${s}
              %endif
              %endfor
            %else:
            ${status.get('hash') | h}
            %endif
          </div>
          <div class="col">
            <h5>Template engines</h5>
            <ul class="list-group">
            %for template_engine in status.get('template_engines', []):
            <li class="list-group-item">
            %for key, value in template_engine.items():
            %if isinstance(value, list):
            <b>${key_format(key) | h}</b>: ${', '.join(value) | h}<br />
            %elif isinstance(value, dict):
            <b>${key_format(key) | h}</b>:<br />
            %for k, v in value.items():
            &nbsp;&nbsp;&nbsp;&nbsp;${k | h} = ${v | h}<br />
            %endfor
            %else:
            <b>${key_format(key) | h}</b>: ${value | h}<br />
            %endif
            %endfor
            </li>
            %endfor
            </ul>
          </div>
        </div>
        </li>
        %endfor
      </ul>
      %endif
    </div>
  </body>
</html>
