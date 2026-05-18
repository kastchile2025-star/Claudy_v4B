import { Command } from 'commander';
import chalk from 'chalk';
import inquirer from 'inquirer';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs';
import {
  listSkills,
  saveSkillFromContent,
  removeSkill,
  getSkillsDir,
} from '../skills.js';

const execAsync = promisify(exec);

export const skillsCommand = new Command('skills').description('Gestionar skills');

// Convierte URL de GitHub blob a raw
function githubBlobToRaw(url: string): string {
  return url
    .replace('github.com', 'raw.githubusercontent.com')
    .replace('/blob/', '/');
}

skillsCommand
  .command('list')
  .alias('ls')
  .description('Listar skills instalados')
  .action(() => {
    const skills = listSkills();

    if (skills.length === 0) {
      console.log(chalk.gray('\nNo tienes skills instalados.\n'));
      console.log(chalk.cyan('Instala uno con:'));
      console.log(chalk.gray('  claudy skills install <url-a-SKILL.md>'));
      console.log(chalk.gray('  claudy skills install-uipro    # UI/UX Pro Max\n'));
      return;
    }

    console.log(chalk.cyan.bold(`\n📚 Skills instalados (${skills.length}):\n`));
    skills.forEach((s) => {
      console.log(chalk.yellow(`▸ ${s.name}`));
      console.log(chalk.gray(`  ${s.description}`));
      console.log(chalk.gray(`  ${s.path}\n`));
    });
  });

skillsCommand
  .command('install <url>')
  .description('Instalar skill desde URL de SKILL.md (raw o blob)')
  .option('-n, --name <name>', 'Nombre del skill (default: derivado de URL)')
  .action(async (url: string, options) => {
    const rawUrl = githubBlobToRaw(url);

    console.log(chalk.cyan(`Descargando ${rawUrl}...`));

    try {
      const res = await fetch(rawUrl);
      if (!res.ok) {
        console.log(chalk.red(`✗ Error ${res.status}: ${res.statusText}`));
        process.exit(1);
      }

      const content = await res.text();
      const name =
        options.name ||
        path
          .basename(rawUrl, '.md')
          .replace(/SKILL/i, '')
          .replace(/^[-_]+|[-_]+$/g, '') ||
        'skill-' + Date.now().toString(36);

      const filePath = saveSkillFromContent(name, content);
      console.log(chalk.green(`✓ Skill "${name}" instalado en:`));
      console.log(chalk.gray(`  ${filePath}\n`));
    } catch (err: any) {
      console.log(chalk.red('✗ Error: ' + err.message));
      process.exit(1);
    }
  });

skillsCommand
  .command('install-uipro')
  .description('Instalar UI/UX Pro Max skill (vía npx uipro-cli)')
  .action(async () => {
    const skillsDir = getSkillsDir();
    const tmpDir = path.join(skillsDir, '_uipro_tmp');
    fs.mkdirSync(tmpDir, { recursive: true });

    console.log(chalk.cyan('🎨 Instalando UI/UX Pro Max via uipro-cli...'));
    console.log(chalk.gray('   Ejecutando: npx uipro-cli init --ai opencode\n'));

    try {
      const { stdout, stderr } = await execAsync(
        'npx -y uipro-cli init --ai opencode',
        { cwd: tmpDir, timeout: 120_000 }
      );
      console.log(chalk.gray(stdout));
      if (stderr) console.log(chalk.gray(stderr));

      // Buscar el SKILL.md generado
      const generatedPath = path.join(
        tmpDir,
        '.opencode',
        'skills',
        'ui-ux-pro-max',
        'SKILL.md'
      );

      if (!fs.existsSync(generatedPath)) {
        console.log(
          chalk.yellow(
            `⚠ No se encontró SKILL.md generado en ${generatedPath}.\n  Puede que el comando haya cambiado de path.`
          )
        );
        return;
      }

      const content = fs.readFileSync(generatedPath, 'utf-8');
      const filePath = saveSkillFromContent('ui-ux-pro-max', content);

      // Copiar también scripts/ y data/ si existen
      const sourceDir = path.dirname(generatedPath);
      const targetDir = path.dirname(filePath);
      for (const sub of ['scripts', 'data']) {
        const src = path.join(sourceDir, sub);
        const dst = path.join(targetDir, sub);
        if (fs.existsSync(src)) {
          fs.cpSync(src, dst, { recursive: true });
        }
      }

      // Limpiar tmp
      fs.rmSync(tmpDir, { recursive: true, force: true });

      console.log(chalk.green(`\n✓ Skill "ui-ux-pro-max" instalado`));
      console.log(chalk.gray(`  ${filePath}`));
      console.log(chalk.cyan('\nÚsalo en chat:'));
      console.log(chalk.gray('  claudy chat'));
      console.log(
        chalk.gray('  > diseña una landing con UI moderna estilo glassmorphism\n')
      );
    } catch (err: any) {
      console.log(chalk.red('✗ Error: ' + err.message));
      console.log(
        chalk.yellow(
          '\nAsegúrate de tener Node.js + npm. Si falla npx, intenta:\n  npm install -g uipro-cli\n  uipro-cli init --ai opencode'
        )
      );
    }
  });

skillsCommand
  .command('remove <name>')
  .alias('rm')
  .description('Eliminar un skill')
  .option('-f, --force', 'Sin confirmación')
  .action(async (name: string, options) => {
    if (!options.force) {
      const { confirm } = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'confirm',
          message: `¿Eliminar skill "${name}"?`,
          default: false,
        },
      ]);
      if (!confirm) {
        console.log(chalk.gray('Cancelado.'));
        return;
      }
    }

    const removed = await removeSkill(name);
    if (removed) {
      console.log(chalk.green(`✓ Skill "${name}" eliminado`));
    } else {
      console.log(chalk.red(`✗ Skill "${name}" no encontrado`));
    }
  });

skillsCommand
  .command('show <name>')
  .description('Ver el contenido de un skill')
  .action((name: string) => {
    const skill = listSkills().find((s) => s.name === name);
    if (!skill) {
      console.log(chalk.red(`✗ Skill "${name}" no encontrado`));
      process.exit(1);
    }
    console.log(chalk.cyan.bold(`\n📚 ${skill.name}\n`));
    console.log(chalk.gray(skill.description));
    console.log(chalk.gray('─────────────────────────────────────────'));
    console.log(skill.content);
  });
