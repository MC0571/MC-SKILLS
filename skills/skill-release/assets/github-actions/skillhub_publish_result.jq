if type != "object" then
  error("SkillHub publish response must be a JSON object")
elif .success == false then
  error("SkillHub publish response reported success=false")
else
  {name: $name} + (if $slug == "" then {} else {slug: $slug} end) + {
    version: $version,
    skillId: (if (.skillId | type) == "string" or (.skillId | type) == "number" then .skillId else null end),
    status: (if (.status | type) == "string" and .status != "" then .status else "submitted" end),
    publicUrl: (if (.publicUrl | type) == "string" then .publicUrl else null end)
  }
end
