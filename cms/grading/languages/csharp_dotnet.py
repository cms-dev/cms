#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""C# programming language definition, using the Microsoft .NET SDK
and runtime installed in the system.

"""

from cms.grading import Language
from cms.grading.Sandbox import Sandbox


__all__ = ["CSharpDotnet"]


class CSharpDotnet(Language):
    """This defines the C# programming language, compiled and executed with the
    Microsoft .NET SDK.

    """

    @property
    def name(self):
        """See Language.name."""
        return "C# / dotnet"

    @property
    def source_extensions(self):
        """See Language.source_extensions."""
        return [".cs"]

    @property
    def executable_extension(self):
        """See Language.executable_extension."""
        return ".csz"

    @property
    def requires_multithreading(self):
        """See Language.requires_multithreading."""
        return True

    def get_compilation_commands(self,
                                 source_filenames, executable_filename,
                                 for_evaluation=True):
        """See Language.get_compilation_commands."""
        make_csproj = f"""\
echo '<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <Configuration>Release</Configuration>
  </PropertyGroup>
</Project>' >project.csproj
echo '<configuration>
 <packageSources>
    <clear />
 </packageSources>
</configuration>' >nuget.config"""
        make_csproj_full = ['/usr/bin/bash', '-c', make_csproj]
        envs = [
            "DOTNET_CLI_TELEMETRY_OPTOUT=1",
            "DOTNET_NOLOGO=1",
            "DOTNET_SKIP_WORKLOAD_INTEGRITY_CHECK=1",
        ]
        do_build = ['/usr/bin/env', *envs, '/usr/bin/dotnet', 'build', '-o', 'out', 'project.csproj']
        do_zip = ['/usr/bin/zip', '-r', executable_filename, 'out']
        return [make_csproj_full, do_build, do_zip]

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        """See Language.get_evaluation_commands."""
        return [['/usr/bin/unzip', executable_filename],
                ['/usr/bin/dotnet', 'out/project.dll']]
