"""Dependency-free member Workflow selection page."""

# The inline HTML/CSS/JavaScript is shipped as one package-safe string.
# ruff: noqa: E501

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shared Workflow Catalog</title>
<style>
body{font:16px system-ui;margin:0;background:#f5f7fb;color:#172033}main{max-width:960px;margin:auto;padding:32px}
header,section{background:white;border:1px solid #dce2ea;border-radius:14px;padding:20px;margin-bottom:18px}
label{display:block;font-weight:650;margin-bottom:8px}input{padding:10px;width:min(420px,90%)}button{padding:8px 12px;margin-left:8px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #e7ebf0}.muted{color:#5e6a7e}
</style></head>
<body><main><header><h1>Shared Workflow Catalog</h1>
<p class="muted">Choose which published Workflow this bound Bridge may synchronize. Selection does not grant execution permission.</p>
<label for="bridge">Bridge ID</label><input id="bridge" autocomplete="off"><button id="load">Load</button><p id="status"></p></header>
<section><table><thead><tr><th>Workflow</th><th>Owner</th><th>Visibility</th><th>Selection</th></tr></thead><tbody id="rows"></tbody></table></section>
</main><script>
const params=new URLSearchParams(location.hash.slice(1));let bearer=params.get("session")||"";const invitation=params.get("invitation")||"";
if(location.hash)history.replaceState(null,"",location.pathname);
async function call(path,body){const response=await fetch(path,{method:"POST",headers:{"Authorization":"Bearer "+bearer,"Content-Type":"application/json"},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw new Error(data.code||"request_failed");return data}
async function signIn(){if(!invitation)return;const response=await fetch("/v1/member/sign-in",{method:"POST",headers:{"Authorization":"Invitation "+invitation}});const data=await response.json();if(!response.ok){document.querySelector("#status").textContent="Sign in failed: "+(data.code||"request_failed");return}bearer=data.session;document.querySelector("#status").textContent="Signed in. Enter the Bridge ID to load Workflows."}
async function load(){const bridge=document.querySelector("#bridge").value.trim();const status=document.querySelector("#status");if(!bearer){status.textContent="Sign in to the shared platform to open a member session.";return}try{const data=await call("/v1/member/catalog",{bridge_id:bridge});const rows=document.querySelector("#rows");rows.textContent="";for(const entry of data.entries){const id=entry.package.metadata.identity;const tr=document.createElement("tr");const button=document.createElement("button");button.textContent=entry.selected?"Revoke":"Select";button.onclick=async()=>{await call(entry.selected?"/v1/member/revoke":"/v1/member/select",{bridge_id:bridge,asset:id});await load()};for(const value of [`${id.namespace}/${id.name}@${id.version}`,`${entry.package.metadata.owner.type}:${entry.package.metadata.owner.id}`,entry.package.metadata.visibility]){const td=document.createElement("td");td.textContent=value;tr.append(td)}const action=document.createElement("td");action.append(button);tr.append(action);rows.append(tr)}status.textContent=`${data.entries.length} Workflow(s)`}catch(error){status.textContent=`Unavailable: ${error.message}`}}
document.querySelector("#load").onclick=load;
void signIn();
</script></body></html>"""
