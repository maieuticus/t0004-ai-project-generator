# Java starter

The starter requires Eclipse Temurin JDK 25. The official Maven Wrapper uses
Maven 3.9.11 and verifies its distribution against the SHA-256 in
`.mvn/wrapper/maven-wrapper.properties`. Its first invocation downloads Maven;
the build also downloads plugins and test dependencies from Maven repositories.

From `java/`, run `sh mvnw verify` on Unix or `mvnw.cmd verify` on Windows.
Run the example with `java -jar target/project-java-starter-0.1.0.jar`.
`verify` compiles the project, runs the JUnit tests, and builds the executable JAR.

The fixed versions and archive timestamp support repeatable builds. Maven does
not provide an npm-style integrity lockfile for the complete dependency graph;
repository contents, JDK patch versions and environment can still affect results.
Generated files in `target/` are ignored. Adapt the package name and coordinates
to the project before building on the starter.
